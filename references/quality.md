# Quality and delivery

Use the `SKILL_ROOT` and `PROJECT` absolute-path convention from SKILL.md; do not resolve scripts or output relative to the current working directory.

## Run objective checks

Run `python3 "$SKILL_ROOT/scripts/project_state.py" show "$PROJECT" > "$PROJECT/preview/project-state.json"`, read the four `spec` values with the agent's JSON reader, then run `python3 "$SKILL_ROOT/scripts/media_qc.py" "$PROJECT/output/final-vertical.mp4" --json --width WIDTH --height HEIGHT --min-duration MIN --max-duration MAX`. Replace every placeholder so the flags match project-state spec exactly. Do not depend on jq. Accept at least one audio stream. Treat these as objective technical measurements, not proof of visual, narrative, or perceptual quality.

Review the returned measurements and every failure. Also inspect the render for clipping, caption overflow, silent gaps, abrupt cuts, illegible text, synchronization errors, and unintended blank frames; label these as manual observations.

Run a full 解码 check separately because `media_qc.py` verifies only metadata and the existence of an audio stream: `ffmpeg -v error -i "$PROJECT/output/final-vertical.mp4" -f null -`. This proves decodability, not creative quality.

Inspect 主体裁切, faces, products, logos, UI safe areas, 切点爆音, 黑帧, frozen frames, 字幕错字, 断句, layout, overflow, and narration synchronization. For HyperFrames work, run and record HyperFrames lint, HyperFrames validate, and HyperFrames inspect before final render.

Copy `covers/selected.png` to `output/cover.png` with an atomic local copy. Then 校验 bytes are identical; fail delivery if either file is absent or their bytes differ.

## Repair within a bound

1. Identify the smallest change that addresses each failure.
2. Re-render only affected stages when practical.
3. Re-run media QC against the new final file.
4. Stop after at most 3 repair rounds. For every remaining failure, report a 诊断, likely cause, and 可复现命令 that demonstrates the failure without changing external state.

Never hide a failed check, relax thresholds without user approval, or claim that metadata proves creative quality.

Before delivery, replace every `<from project-state.json ...>` production-report placeholder with the recorded state value. Check that the final report contains no `<from project-state.json` text; treat any remaining placeholder as a delivery failure.

Complete the production report with every asset 来源, generation method, modification, and 版权/license status, including ImageGen, BGM, SFX, fonts, footage, voices, and brand material.

## Deliver

Provide:

- the final video and selected cover paths;
- `output/final-vertical.mp4`, `output/cover.png`, and `output/subtitles.srt`;
- the standalone SRT and any burned-in subtitle version;
- the approved title, script, and storyboard paths;
- `output/production-report.md`;
- editable HyperFrames project/source and the reviewed FFmpeg commands or scripts;
- raw intermediate assets needed to reproduce the edit;
- the two unselected covers as `covers/cover-a.png`, `cover-b.png`, or `cover-c.png` alongside the selected candidate;
- objective ffprobe measurements and repair-round count;
- missing optional local tools or substitutions used;
- unresolved technical or manual-review concerns;
- relevant copyright, paid-service, and privacy assumptions.
