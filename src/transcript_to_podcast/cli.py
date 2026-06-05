"""Command-line interface for transcript-to-podcast."""

from __future__ import annotations

import argparse
import asyncio
import sys

from . import core


def _parse_voice_overrides(pairs: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise argparse.ArgumentTypeError(
                f"--voice expects NAME=VOICE, got {pair!r}"
            )
        name, voice = pair.split("=", 1)
        mapping[name.strip()] = voice.strip()
    return mapping


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="transcript-to-podcast",
        description="Turn a two-host markdown transcript into a two-voice MP3 "
        "podcast using edge-tts (free Microsoft neural voices) and ffmpeg.",
    )
    p.add_argument("transcript", nargs="?", help="path to the markdown transcript")
    p.add_argument("-o", "--output", help="output MP3 path")
    p.add_argument(
        "--voice", action="append", default=[], metavar="NAME=VOICE",
        help="map a speaker to a voice, e.g. --voice Maya=en-US-AvaNeural "
        "(repeatable; unmapped speakers get distinct pool voices)",
    )
    p.add_argument("--gap", type=float, default=0.45,
                   help="seconds of silence between turns (default: 0.45)")
    p.add_argument("--rate", default="+0%",
                   help="speech rate passed to edge-tts, e.g. -7%% or +10%% "
                   "(default: +0%%)")
    p.add_argument("--concurrency", type=int, default=4,
                   help="parallel synthesis requests (default: 4)")
    p.add_argument("--title", help="ID3 title (default: output filename)")
    p.add_argument("--keep-clips", action="store_true",
                   help="keep the per-turn clips and temp dir for debugging")
    p.add_argument("--dry-run", action="store_true",
                   help="parse and report turns/voices without synthesizing")
    p.add_argument("--list-voices", action="store_true",
                   help="list available en-* neural voices and exit")
    return p


def main() -> None:
    args = build_parser().parse_args()

    if args.list_voices:
        for v in asyncio.run(core.list_voices("en-")):
            print(f"{v['ShortName']:32} {v['Gender']:7} {v.get('Locale','')}")
        return

    if not args.transcript:
        build_parser().error("transcript path is required (unless --list-voices)")

    overrides = _parse_voice_overrides(args.voice)

    if args.dry_run:
        with open(args.transcript, encoding="utf-8") as fh:
            turns = core.parse_transcript(fh.read(), list(overrides.keys()))
        if not turns:
            build_parser().error(f"no speaker turns found in {args.transcript}")
        voices = core.resolve_voices([t.speaker for t in turns], overrides)
        words = sum(len(t.text.split()) for t in turns)
        counts: dict[str, int] = {}
        for t in turns:
            counts[t.speaker] = counts.get(t.speaker, 0) + 1
        print(f"Turns: {len(turns)}  |  words: {words}  "
              f"(~{words/140:.1f} min at 140 wpm)")
        for speaker, voice in voices.items():
            print(f"  {speaker:12} -> {voice:28} ({counts[speaker]} turns)")
        return

    if not args.output:
        build_parser().error("-o/--output is required when synthesizing")

    try:
        result = core.build_podcast(
            transcript_path=args.transcript,
            out_path=args.output,
            voice_overrides=overrides,
            gap_sec=args.gap,
            rate=args.rate,
            concurrency=args.concurrency,
            title=args.title,
            keep_clips=args.keep_clips,
        )
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)

    voices_str = ", ".join(f"{k}={v}" for k, v in result.voices.items())
    dur = result.duration_sec
    dur_str = f"{int(dur // 60)}m {int(dur % 60)}s" if dur else "unknown"
    print(f"Wrote {result.out_path}")
    print(f"  turns: {result.n_turns}  |  duration: {dur_str}")
    print(f"  voices: {voices_str}")


if __name__ == "__main__":
    main()
