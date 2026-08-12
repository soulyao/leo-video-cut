---
name: leo-video-cut
description: Use when producing or resuming a Chinese vertical short-video project that needs explicit title, cover, and storyboard approval gates, local-first media production, and objective delivery checks.
---

# Leo Video Cut

Produce a traceable 1080x1920 Chinese vertical video lasting 30–60 seconds. Preserve project state and user approvals instead of hiding decisions inside chat.

## Route the input

Classify the request into one of four routes: text/topic, local document, local media, or existing project. Read [the workflow reference](references/workflow.md) for exact routing and resume behavior. Ask only for information that blocks a safe start; otherwise record assumptions in `brief.md`.

Check copyright, paid-service, and privacy authorization before using supplied or third-party material. Keep production local unless the user explicitly authorizes a different tool or service.

## Initialize or resume

Resolve `SKILL_ROOT` first as the absolute path of the directory containing the current SKILL.md. Resolve `PROJECT` separately as an absolute project path inside the user workspace. Never create PROJECT inside SKILL_ROOT. Use these absolute paths regardless of the current working directory.

Run the environment report before production:

```bash
python3 "$SKILL_ROOT/scripts/check_environment.py" --json
```

Initialize a new project without overwriting an existing path, or resume from its state:

```bash
python3 "$SKILL_ROOT/scripts/project_state.py" init "$PROJECT"
python3 "$SKILL_ROOT/scripts/project_state.py" show "$PROJECT"
```

Follow `project-state.json` as the source of truth. Keep the default specification at 1080 by 1920 pixels and 30 to 60 seconds. When the user requests another format, pass positive `--width`, `--height`, `--min-duration`, and `--max-duration` values to `init`; keep the minimum no greater than the maximum.

## Enforce the three hard gates

Follow these hard gates in order. Never infer approval from silence.

1. Draft exactly three numbered title candidates (one, two, three), save them to `title/candidates.md`, present them, and stop. After the user chooses or edits one, run `python3 "$SKILL_ROOT/scripts/project_state.py" approve-title "$PROJECT" --title "TITLE"`.
2. Read and use the built-in ImageGen skill by default. Generate exactly three meaningfully different covers for the same approved title; vary composition and visual direction, not the title. Save only `covers/cover-a.png`, `covers/cover-b.png`, and `covers/cover-c.png`, present all three, and stop. After the user chooses one, run `python3 "$SKILL_ROOT/scripts/project_state.py" select-cover "$PROJECT" --cover cover-a.png` with the chosen filename.
3. Write `script/script.md` and `script/storyboard.md` only after the cover choice. Present both, and stop. After explicit approval, run `python3 "$SKILL_ROOT/scripts/project_state.py" approve-storyboard "$PROJECT"`.

Treat explicit `--direct` as the only pause bypass. Use it only when the user explicitly requests direct or unattended completion:

Treat phrases such as “赶时间”, “你自己决定”, or “少问问题” as urgency or discretion only; they do not count as direct authorization. Require an explicit request to continue without waiting, finish unattended, or bypass later pauses.

```bash
python3 "$SKILL_ROOT/scripts/project_state.py" init "$PROJECT" --direct
python3 "$SKILL_ROOT/scripts/project_state.py" direct "$PROJECT"
```

Use `direct "$PROJECT"` to switch an existing gated project to unattended work while preserving completed approvals. Keep every title, cover, script, and storyboard artifact in direct mode. Direct mode must still generate exactly three covers (`cover-a.png`, `cover-b.png`, and `cover-c.png`), then auto-select one before continuing. After creating each automatic artifact, run `python3 "$SKILL_ROOT/scripts/project_state.py" record-artifact "$PROJECT" --name NAME --path PATH` and pass `--value` for the chosen title when useful. Treat `pending_auto` as permission to complete an artifact automatically, never as proof that it already exists.

## Produce locally

After the three gates, produce narration, timing, visuals, motion, captions, mix, and render. Prefer local Whisper for transcription/alignment, local TTS (including macOS `say`) for narration, HyperFrames for motion when locally available, and FFmpeg/ffprobe for assembly and inspection. Read [the local production reference](references/local-production.md) before invoking these tools.

Never install, download, purchase, upload, or call a remote API without explicit authorization. Never expose environment-variable values or private source content.

## Check and repair

Run objective delivery QC:

```bash
python3 "$SKILL_ROOT/scripts/project_state.py" show "$PROJECT" > "$PROJECT/preview/project-state.json"
python3 "$SKILL_ROOT/scripts/media_qc.py" "$PROJECT/output/final-vertical.mp4" --json --width WIDTH --height HEIGHT --min-duration MIN --max-duration MAX
```

Read `spec.width`, `spec.height`, `spec.duration_min`, and `spec.duration_max` from the cached JSON with the agent's JSON reader, then replace `WIDTH`, `HEIGHT`, `MIN`, and `MAX` before running QC. Make all four flags match project-state spec exactly. Do not depend on jq or shell interpolation of untrusted JSON.

Fix reported codec, size, duration, readability, or audio failures. Allow at most 3 repair rounds; then report the remaining failures instead of looping. Do not claim perceptual or editorial quality from metadata checks. Read [the quality reference](references/quality.md) for the acceptance and repair procedure.

## Deliver the project

Deliver `output/final-vertical.mp4`, `output/cover.png`, `output/subtitles.srt`, and `output/production-report.md` together with the approved title, selected cover, script, storyboard, editable HyperFrames/FFmpeg source, raw intermediate assets, two unselected covers, measured QC results, tool limitations, and unresolved issues. Keep intermediate files inside the project and do not modify unrelated media.
