# Local production

Use the `SKILL_ROOT` and `PROJECT` absolute-path convention from SKILL.md. Resolve every bundled script from `$SKILL_ROOT/scripts` and every generated artifact from the absolute user-workspace `$PROJECT` path.

## Prepare

Run `python3 "$SKILL_ROOT/scripts/check_environment.py" --json`. Require FFmpeg and ffprobe. Treat Whisper, local TTS, Node/npx, and HyperFrames as optional local capabilities and follow the report's local installation guidance when the user authorizes installation.

Do not run `--probe` unless a version check is necessary. The HyperFrames npx probe uses `--no-install`; never permit npx to fetch a package.

## Build assets

- Use the approved title consistently on all downstream artifacts.
- Prefer authorized user 人物, 产品, and 品牌素材 for covers. When those are insufficient, gather 视觉参考 and read the built-in ImageGen skill before generating 原创 covers. Generate exactly three distinct compositions and save them as the fixed candidate filenames. Check every cover for 标题可读, UI 安全区, 人物和产品完整, and 与视频风格一致.
- Use ImageGen for original B-roll, 背景, and 插图 when the approved storyboard needs visuals unavailable in supplied assets. Keep provenance in the production report.
- Write narration for 30–60 seconds and keep claims grounded in the brief.
- Use a local TTS engine for narration when requested. Use local Whisper for transcription or timestamp alignment; do not recommend a hosted transcription API. After Whisper, 校对错字, 断句, timing, and 字幕布局 rather than accepting raw output.
- Build readable Chinese captions with safe margins for the recorded project dimensions. Export an SRT alongside any burned-in captions.
- Use HyperFrames locally for purposeful motion, typography, title cards, or overlays when available.
- Use FFmpeg with explicit argv or a reviewed command to assemble H.264 video and an audio track.

## Mix and decode

- Add licensed or original BGM and SFX only when they support the edit. Record each source and license.
- Use a voice-first mix: apply ducking under narration, prevent masking, and loudness normalize the final program without clipping.
- Verify that video and every 人声/音轨 are actually decodable; metadata presence alone is insufficient. Run `ffmpeg -v error -i "$PROJECT/output/final-vertical.mp4" -f null -` and treat any stderr decode error as a failed delivery check.

## Protect rights and privacy

- Confirm that the user owns or may use supplied footage, music, fonts, voices, likenesses, logos, and generated assets.
- Ask before using a paid tool, purchasing a license, or accepting billable work.
- Ask before uploading private material or sending it to any remote service.
- Avoid imitating a real person's voice or likeness without explicit permission.
- Require 单独明确授权 before altering 真人身份 or 面部特征, including face replacement, identity transfer, beautification that changes identity, or expression reconstruction.
- Preserve originals and write derived output only inside the project.
