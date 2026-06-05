# transcript-to-podcast

Turn a two-host (or N-host) **markdown dialogue transcript** into a **multi-voice MP3
podcast** using [edge-tts](https://github.com/rany2/edge-tts) (free Microsoft neural
voices, no API key) and `ffmpeg`.

It beats "read it aloud in the browser / ChatGPT" because each speaker gets a
**distinct voice**, the speaker labels / timestamps / markdown are **stripped** (never
read out loud), turns are separated by natural pauses, and you get a real **file** you
can put on your phone.

## Requirements

- Python ≥ 3.10 (managed by [uv](https://docs.astral.sh/uv/))
- `ffmpeg` and `ffprobe` on `PATH` (system packages, not pip):
  `sudo apt install ffmpeg`
- Internet access (edge-tts streams from Microsoft's neural voice service)

## Install / run

This is a [uv](https://docs.astral.sh/uv/) project — dependencies and the Python
version are pinned in `pyproject.toml` + `uv.lock`.

```bash
uv sync                 # create .venv and install locked deps
uv run transcript-to-podcast --help
```

## Transcript format

A "turn" is any paragraph starting with a **bold speaker label**:

```markdown
**Maya:** Okay, so let's get into it.
**Theo:** Sure — and here's the part that surprised me.
```

Everything else (front-matter, `#` headings, `[00:00]` timestamps, `>` callouts,
`## Related notes`, …) is ignored. Wrapped lines under a speaker are joined into the
same turn until a blank line or heading.

## Usage

```bash
# Two named voices, output MP3
uv run transcript-to-podcast transcript.md -o podcast.mp3 \
    --voice Maya=en-US-AvaNeural \
    --voice Theo=en-US-AndrewNeural

# Preview parsing + voice assignment without synthesizing (no network)
uv run transcript-to-podcast transcript.md --dry-run

# Slow it down ~7% and widen the gaps
uv run transcript-to-podcast transcript.md -o podcast.mp3 --rate -7% --gap 0.6

# Browse available English neural voices
uv run transcript-to-podcast --list-voices | grep en-US
```

Speakers you don't map explicitly are auto-assigned distinct voices from a
female/male-alternating pool, so a 2-host show sounds like a conversation by default.

### Options

| Flag | Default | Meaning |
|------|---------|---------|
| `-o, --output` | — | output MP3 path (required to synthesize) |
| `--voice NAME=VOICE` | pool | map a speaker to an edge-tts voice (repeatable) |
| `--gap` | `0.45` | seconds of silence between turns |
| `--rate` | `+0%` | edge-tts speech rate, e.g. `-7%`, `+10%` |
| `--concurrency` | `4` | parallel synthesis requests |
| `--title` | filename | ID3 title |
| `--keep-clips` | off | keep per-turn clips + temp dir |
| `--dry-run` | off | parse/report only, no network |
| `--list-voices` | off | list `en-*` neural voices and exit |

## Try the example

```bash
uv run transcript-to-podcast examples/sample-dialogue.md -o /tmp/sample.mp3
```

## How it works

1. Parse the markdown into ordered `(speaker, text)` turns; strip markdown.
2. Synthesize each turn with its speaker's voice via edge-tts (concurrent, with retry).
3. Stitch the clips with short silences into one MP3 via `ffmpeg`.

## Repository layout

```
transcript-to-podcast/
├── src/transcript_to_podcast/   # CLI package: cli.py (args) + core.py (parse → synth → stitch)
├── skill/SKILL.md               # bundled agent skill that wraps this CLI
├── examples/sample-dialogue.md  # tiny smoke-test transcript
├── pyproject.toml, uv.lock      # uv-managed deps, Python ≥ 3.10
└── README.md
```

## Bundled skill

`skill/SKILL.md` is an agent skill (Claude Code / compatible agents) that documents
how to drive this CLI. It is the single source of truth, installed into agent skill
folders as **gitignored symlinks** back to this repo — so editing it updates every
install, and the skill is correctly absent anywhere this repo isn't checked out.
Example (Zettelkasten vault):

```bash
ln -s "$PWD/skill" /path/to/vault/.claude/skills/transcript-to-podcast
ln -s "$PWD/skill" /path/to/vault/.agents/skills/transcript-to-podcast
```

### Where transcripts live

Generated transcripts for the two-host **Socrates** series are organized in the
vault under `Socrates-podcasts/` — a dedicated folder holding one markdown file per
episode, each linked back from its source literature note. The rendered MP3s are
kept outside the git-synced vault (e.g. `~/Downloads/`) so audio binaries don't
bloat the repo.

## License

MIT
