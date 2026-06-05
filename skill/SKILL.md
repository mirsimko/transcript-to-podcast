---
name: transcript-to-podcast
description: >-
  Convert a markdown dialogue/transcript into a multi-voice MP3 podcast — one
  distinct neural voice per speaker — using the local transcript-to-podcast CLI
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
pauses are inserted between turns. The result is a real file the user can drop on
their phone.

The actual logic lives in the **uv project this skill ships with**, at
`/home/miro/dev/transcript-to-podcast` (this `SKILL.md` is bundled in that repo
under `skill/`; the vault installs are gitignored symlinks back to it). This skill
is a thin wrapper: it tells you how to drive that CLI well. Don't reimplement TTS
inline — call the tool.

## Why this beats "just read it aloud"

A two-host transcript read by one voice stops sounding like a conversation, and
the engine ends up speaking "Maya colon", "open bracket zero zero", etc. This
tool assigns a contrasting voice per speaker, removes all the scaffolding, and
produces a portable MP3. That is almost always what the user actually wants when
they say "podcast".

## Prerequisites (check before running)

- The uv project exists at `/home/miro/dev/transcript-to-podcast`. If it is
  missing, it can be recreated with `uv init --package` + `uv add edge-tts`, but
  normally it is already there.
- `ffmpeg` and `ffprobe` are on `PATH` (used to stitch clips). `sudo apt install
  ffmpeg` if not.
- Network access — edge-tts streams from Microsoft's free neural-voice service
  (no API key needed).

## Transcript format

A "turn" is any paragraph that starts with a **bold speaker label**:

```markdown
**Maya:** Okay, so let's get into it.
**Theo:** Sure — and here's the part that surprised me.
```

Everything else (front-matter, `#` headings, `[00:00]` timestamps, `>` callouts,
a trailing `## Related notes` section, etc.) is ignored. A label only counts as a
speaker if it is passed via `--voice` **or** it recurs (≥ 2 turns), so one-off
header lines like `**Source paper:**` or `**Hosts:**` are correctly skipped.

## How to run it

Always invoke through uv so the locked deps/venv are used. `--project` lets you
run from any directory:

```bash
uv run --project /home/miro/dev/transcript-to-podcast transcript-to-podcast \
  "<path/to/transcript.md>" -o "<path/to/output.mp3>" \
  --voice Maya=en-US-AvaNeural --voice Theo=en-US-AndrewNeural
```

### Recommended workflow

1. **Dry-run first** to confirm the parse — how many turns, which speakers, the
   word count / rough minutes — without any network calls:
   ```bash
   uv run --project /home/miro/dev/transcript-to-podcast transcript-to-podcast \
     "<transcript.md>" --dry-run
   ```
   If the speaker list looks wrong (e.g. a header label leaked in), pin the real
   speakers explicitly with `--voice NAME=VOICE` so detection is strict.
2. **Pick voices.** For a 2-host show, a contrasting female/male pair reads best.
   Good defaults: `en-US-AvaNeural` + `en-US-AndrewNeural` (Microsoft's most
   natural conversational voices). Unmapped speakers are auto-assigned distinct
   pool voices, so you can skip `--voice` and still get two different voices.
   Browse options with `--list-voices` (filter `en-US`).
3. **Synthesize** to an MP3 with `-o`.
4. **Report** the output path and duration back to the user.

### Output location — do NOT write the MP3 into the vault

The zettelkasten vault auto-syncs to GitHub every 15 minutes; a ~10–20 MB audio
binary does not belong in it. Write the MP3 to `~/Downloads/` (on this machine
`~/Downloads` is symlinked to the Windows Downloads folder, so it opens with a
double-click), or another location outside the git repo. Only the transcript
markdown belongs in the vault.

## Tuning

| Need | Flag |
|------|------|
| Longer/shorter runtime | `--rate` (e.g. `-7%` slower, `+10%` faster) |
| Bigger pauses between turns | `--gap 0.6` (seconds; default `0.45`) |
| Faster build | `--concurrency 6` |
| Set the MP3 title | `--title "Episode title"` |
| Keep per-turn clips to debug | `--keep-clips` |

Rough pacing: edge-tts at default rate runs ~150 wpm, so ~2,700 spoken words ≈
18 min. To hit a target length, estimate from the dry-run word count and nudge
`--rate`.

## Worked example

Convert the vault's CV-engineer podcast transcript:

```bash
uv run --project /home/miro/dev/transcript-to-podcast transcript-to-podcast \
  "/mnt/c/Users/mirsi/OneDrive/Dokumenty/miro_vault/zettelkasten/Literature notes/2026-06-05 Towards end-to-end automation of AI research — CV podcast transcript.md" \
  -o ~/Downloads/ai-scientist-cv-podcast.mp3 \
  --voice Maya=en-US-AvaNeural --voice Theo=en-US-AndrewNeural
```

## Troubleshooting

- **"No '**Speaker:** ...' turns found"** — the transcript doesn't use bold
  speaker labels at line start, or the only labels are one-offs. Add at least one
  `--voice NAME=VOICE` so that name is treated as a speaker.
- **A header line shows up as a speaker in `--dry-run`** — pass the real speakers
  via `--voice` to switch detection to strict mode.
- **ffmpeg/ffprobe not found** — install ffmpeg; it's a system dependency, not a
  pip package.
- **Mispronounced acronyms** (e.g. "GPT-4o", "o4-mini") — minor; if it matters,
  edit the transcript to a phonetic spelling for that line, then re-run.
