"""Parse a markdown dialogue transcript, synthesize per-speaker voices, stitch to MP3.

A "turn" is a paragraph that begins with a bold speaker label, e.g.

    **Maya:** Okay, so let's get into it.
    **Theo:** Sure — here's the thing.

Everything that is not a speaker turn (headings, timestamps, block quotes,
front-matter, "Related notes", etc.) is ignored.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass

import edge_tts

# Pool used to auto-assign voices to speakers that the caller did not map.
# Alternates female/male so a 2-host show gets contrasting voices by default.
DEFAULT_VOICE_POOL = [
    "en-US-AvaNeural",
    "en-US-AndrewNeural",
    "en-US-EmmaNeural",
    "en-US-BrianNeural",
    "en-US-JennyNeural",
    "en-US-GuyNeural",
]

_SPEAKER_RE = re.compile(r"^\*\*(?P<name>[^*:]+?):\*\*\s*(?P<text>.*)$")
_HEADING_RE = re.compile(r"^\s*(#{1,6}\s|>|---|\*\*\*|___|\||-\s|\d+\.\s)")


@dataclass
class Turn:
    speaker: str
    text: str


def clean_text(text: str) -> str:
    """Strip markdown so the TTS engine never reads syntax out loud."""
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)  # [[a|b]] -> b
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)            # [[a]]   -> a
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)        # [a](url)-> a
    text = re.sub(r"`([^`]*)`", r"\1", text)                    # `code`  -> code
    text = text.replace("**", "").replace("*", "").replace("_", "")
    text = text.replace("—", ", ").replace("–", ", ")          # dashes -> pause
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _speaker_set(
    lines: list[str], known_speakers: list[str] | None
) -> set[str]:
    """Decide which bold labels are real speakers.

    A label counts as a speaker if it is explicitly declared (``--voice NAME=``)
    or it recurs (>= 2 turns). This rejects one-off header labels like
    ``**Source paper:**`` or ``**Hosts:**`` while keeping recurring hosts.
    Falls back to every label if nothing else qualifies.
    """
    counts: dict[str, int] = {}
    for raw in lines:
        m = _SPEAKER_RE.match(raw.rstrip())
        if m:
            name = m.group("name").strip()
            counts[name] = counts.get(name, 0) + 1
    speakers = set(known_speakers or [])
    speakers |= {name for name, c in counts.items() if c >= 2}
    return speakers or set(counts)


def parse_transcript(
    markdown: str, known_speakers: list[str] | None = None
) -> list[Turn]:
    """Extract ordered speaker turns. Continuation lines join the current turn."""
    lines = markdown.splitlines()
    speakers = _speaker_set(lines, known_speakers)
    turns: list[Turn] = []
    current: Turn | None = None
    for raw in lines:
        line = raw.rstrip()
        m = _SPEAKER_RE.match(line)
        if m and m.group("name").strip() in speakers:
            if current and current.text:
                turns.append(current)
            current = Turn(m.group("name").strip(), m.group("text").strip())
        elif current is not None:
            # blank line, heading, or a non-speaker bold label ends the turn
            if not line.strip() or _HEADING_RE.match(line) or m is not None:
                if current.text:
                    turns.append(current)
                current = None
            else:
                current.text = f"{current.text} {line.strip()}".strip()
    if current and current.text:
        turns.append(current)

    cleaned = []
    for t in turns:
        spoken = clean_text(t.text)
        if spoken:
            cleaned.append(Turn(t.speaker, spoken))
    return cleaned


def resolve_voices(
    speakers: list[str], overrides: dict[str, str] | None = None
) -> dict[str, str]:
    """Map each distinct speaker to a voice, honoring overrides, else the pool."""
    overrides = overrides or {}
    mapping: dict[str, str] = {}
    pool_idx = 0
    for speaker in speakers:
        if speaker in mapping:
            continue
        if speaker in overrides:
            mapping[speaker] = overrides[speaker]
        else:
            mapping[speaker] = DEFAULT_VOICE_POOL[pool_idx % len(DEFAULT_VOICE_POOL)]
            pool_idx += 1
    return mapping


async def list_voices(locale_prefix: str | None = "en-") -> list[dict]:
    voices = await edge_tts.list_voices()
    if locale_prefix:
        voices = [v for v in voices if v["ShortName"].startswith(locale_prefix)]
    return sorted(voices, key=lambda v: v["ShortName"])


async def _synth_turn(
    idx: int, turn: Turn, voice: str, rate: str, out_dir: str, sem: asyncio.Semaphore
) -> str:
    path = os.path.join(out_dir, f"turn_{idx:04d}.mp3")
    kwargs = {"rate": rate} if rate and rate != "+0%" else {}
    async with sem:
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                await edge_tts.Communicate(turn.text, voice, **kwargs).save(path)
                if os.path.getsize(path) > 0:
                    return path
            except Exception as exc:  # network hiccups / transient 4xx
                last_exc = exc
                await asyncio.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"failed to synthesize turn {idx}: {last_exc}")


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", *args], check=True, capture_output=True)


def _stitch(clip_paths: list[str], gap_sec: float, out_path: str, title: str) -> None:
    work = os.path.dirname(clip_paths[0])
    silence = os.path.join(work, "silence.mp3")
    _ffmpeg(
        "-f", "lavfi", "-i",
        "anullsrc=channel_layout=mono:sample_rate=24000",
        "-t", str(gap_sec), "-c:a", "libmp3lame", "-q:a", "4", silence,
    )
    listfile = os.path.join(work, "concat.txt")
    with open(listfile, "w", encoding="utf-8") as fh:
        for i, p in enumerate(clip_paths):
            fh.write(f"file '{p}'\n")
            if i != len(clip_paths) - 1:
                fh.write(f"file '{silence}'\n")
    _ffmpeg(
        "-f", "concat", "-safe", "0", "-i", listfile,
        "-c:a", "libmp3lame", "-q:a", "4",
        "-metadata", f"title={title}",
        "-metadata", "comment=Generated by transcript-to-podcast",
        out_path,
    )


def probe_duration(path: str) -> float | None:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return float(out)
    except (subprocess.CalledProcessError, ValueError):
        return None


@dataclass
class BuildResult:
    out_path: str
    n_turns: int
    voices: dict[str, str]
    duration_sec: float | None


def build_podcast(
    transcript_path: str,
    out_path: str,
    voice_overrides: dict[str, str] | None = None,
    gap_sec: float = 0.45,
    rate: str = "+0%",
    concurrency: int = 4,
    title: str | None = None,
    keep_clips: bool = False,
) -> BuildResult:
    """End-to-end: read transcript -> two-voice clips -> stitched MP3."""
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("ffmpeg/ffprobe not found on PATH (required for stitching)")

    with open(transcript_path, encoding="utf-8") as fh:
        turns = parse_transcript(fh.read(), list((voice_overrides or {}).keys()))
    if not turns:
        raise ValueError(f"No '**Speaker:** ...' turns found in {transcript_path}")

    voices = resolve_voices([t.speaker for t in turns], voice_overrides)
    title = title or os.path.splitext(os.path.basename(out_path))[0]
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    work = tempfile.mkdtemp(prefix="t2p_")
    try:
        async def run() -> list[str]:
            sem = asyncio.Semaphore(concurrency)
            tasks = [
                _synth_turn(i, t, voices[t.speaker], rate, work, sem)
                for i, t in enumerate(turns)
            ]
            return await asyncio.gather(*tasks)

        clips = asyncio.run(run())
        _stitch(clips, gap_sec, out_path, title)
    finally:
        if not keep_clips:
            shutil.rmtree(work, ignore_errors=True)

    return BuildResult(out_path, len(turns), voices, probe_duration(out_path))
