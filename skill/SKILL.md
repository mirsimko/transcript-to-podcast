---
name: transcript-to-podcast
description: >-
  Convert a markdown dialogue/transcript into a multi-voice MP3 podcast — one
  distinct neural voice per speaker — using the transcript-to-podcast CLI
  (edge-tts + ffmpeg). Use this WHENEVER the user wants to turn a transcript,
  script, dialogue, interview, or two-host/conversational notes into audio they
  can listen to: "make a podcast from this transcript", "turn these notes into
  audio", "I want to listen to this on a walk", "narrate this dialogue with
  different voices", "two-voice audio version", "read this conversation aloud
  with separate speakers". Strongly prefer this over Chrome reading mode,
  ChatGPT read-aloud, or any single-voice TTS, because those use one voice for
  everyone, read the "**Name:**" labels and timestamps out loud, and leave you
  with no file. Triggers on: podcast, audio version, TTS of a conversation,
  multi-voice narration, listen to a note/transcript/script.
---

# transcript-to-podcast

Turn a markdown **dialogue transcript** (speaker turns marked with bold labels)
into a single **multi-voice MP3** — each speaker gets their own neural voice, the
labels/timestamps/markdown are stripped so they are never spoken, and short
pauses are inserted between turns. The result is a portable audio file.

The logic lives in the **`transcript-to-podcast` uv project** that this skill is
bundled in. This skill is a thin wrapper: locate the CLI, then drive it. Don't
reimplement TTS inline — call the tool.

## Why this beats "just read it aloud"

A two-host transcript read by one voice stops sounding like a conversation, and
the engine ends up speaking "Maya colon", "open bracket zero zero", etc. This
tool assigns a contrasting voice per speaker, removes all the scaffolding, and
produces a portable MP3 — almost always what the user actually wants when they
say "podcast".

## Locating the CLI

This `SKILL.md` ships inside the project at `skill/SKILL.md`, so the **uv project
root is the parent of this skill's directory**. Installs are usually **symlinks**
to that `skill/` folder, so resolve symlinks first. From the directory this skill
loaded from (the harness tells you that path):

```bash
# SKILL_DIR = the directory containing this SKILL.md (given to you on skill load)
PROJECT="$(cd "$(dirname "$(readlink -f "$SKILL_DIR/SKILL.md")")/.." && pwd)"
```

Run every command as `uv run --project "$PROJECT" transcript-to-podcast …`.
(Or install it once with `uv tool install "$PROJECT"`, then call
`transcript-to-podcast` directly from anywhere.)

## Prerequisites

- `uv` (https://docs.astral.sh/uv/) — runs the project with its locked deps/venv.
- `ffmpeg` and `ffprobe` on `PATH` — used to stitch the clips. `sudo apt install ffmpeg`.
- Network access — edge-tts streams from Microsoft's free neural-voice service (no API key).

## Transcript format

A "turn" is any paragraph that starts with a **bold speaker label**:

```markdown
**Maya:** Okay, so let's get into it.
**Theo:** Sure — and here's the part that surprised me.
```

Everything else (front-matter, `#` headings, `[00:00]` timestamps, `>` callouts,
trailing link sections, etc.) is ignored. A label only counts as a speaker if it
is passed via `--voice` **or** it recurs (≥ 2 turns), so one-off header lines like
`**Source:**` or `**Hosts:**` are correctly skipped.

## Workflow

1. **Dry-run first** to confirm the parse — turns, speakers, word count / rough
   minutes — with no network calls:
   ```bash
   uv run --project "$PROJECT" transcript-to-podcast "<transcript.md>" --dry-run
   ```
   If a header label leaks in as a speaker, pin the real speakers with
   `--voice NAME=VOICE` to switch detection to strict mode.
2. **Pick voices.** A contrasting female/male pair reads best for two hosts; good
   defaults are `en-US-AvaNeural` + `en-US-AndrewNeural` (natural conversational
   voices). Unmapped speakers are auto-assigned distinct pool voices, so you can
   omit `--voice` and still get different voices. Browse with `--list-voices`.
3. **Synthesize** to an MP3 with `-o <output.mp3>` (any path you choose).
4. **Report** the output path and duration back to the user.

```bash
uv run --project "$PROJECT" transcript-to-podcast "<transcript.md>" \
  -o "<output.mp3>" \
  --voice Maya=en-US-AvaNeural --voice Theo=en-US-AndrewNeural
```

## Where to write the MP3

Audio is large (~1 MB per minute). If the current workspace is a git repo you
don't want to bloat with binaries, write the MP3 **outside** it (e.g. a downloads
or build/output directory) and keep only the markdown transcript under version
control. Pass any destination with `-o`.

## Tuning

| Need | Flag |
|------|------|
| Longer/shorter runtime | `--rate` (e.g. `-7%` slower, `+10%` faster) |
| Bigger pauses between turns | `--gap 0.6` (seconds; default `0.45`) |
| Faster build | `--concurrency 6` |
| Set the MP3 title | `--title "Episode title"` |
| Keep per-turn clips to debug | `--keep-clips` |

Rough pacing: edge-tts at default rate runs ~150 wpm, so ~2,700 spoken words ≈
18 min. Estimate from the dry-run word count and nudge `--rate` to hit a target.

## Smoke test

The project ships a tiny example transcript:

```bash
uv run --project "$PROJECT" transcript-to-podcast \
  "$PROJECT/examples/sample-dialogue.md" -o /tmp/sample.mp3
```

## Troubleshooting

- **"No '**Speaker:** ...' turns found"** — the transcript doesn't use bold
  speaker labels at line start, or the only labels are one-offs. Add at least one
  `--voice NAME=VOICE` so that name is treated as a speaker.
- **A header line shows up as a speaker in `--dry-run`** — pass the real speakers
  via `--voice` to switch detection to strict mode.
- **ffmpeg/ffprobe not found** — install ffmpeg; it's a system dependency, not pip.
- **Mispronounced acronyms** (e.g. "GPT-4o", "o4-mini") — minor; edit that line in
  the transcript to a phonetic spelling and re-run.
