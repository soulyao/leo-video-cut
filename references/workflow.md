# Workflow and input routing

Use the `SKILL_ROOT` and `PROJECT` absolute-path convention defined in SKILL.md for every command below. Resolve bundled scripts from `$SKILL_ROOT/scripts`; never assume the current working directory is the installed skill, and never place the user's project inside the skill directory.

## Route four input forms

1. **文字**：Treat plain text or a topic as the creative brief. Preserve the original Chinese wording in `brief.md`, record audience and tone assumptions, and build a visual plan from the message.
2. **图片**：Retain originals and turn still images into motion with purposeful 推拉, 平移, 景深, or 视差. Avoid stretching faces, products, logos, or text.
3. **原视频**：Keep the supplied video as the primary source. Run 本地转录, then cut on both 语义 and 音频边界. Remove excessive 停顿, 废话, 失败重拍, 黑帧, and sections with 明显爆音 while preserving meaning and natural cadence.
4. **混合**：When text, 图片, and 原视频 arrive together, keep 原视频为主体. Use text as editorial guidance and still/generated visuals only as supporting inserts, context, or B-roll.

Treat a directory containing `project-state.json` as an existing project regardless of input route. Run `show`, resume at the recorded stage, and never reinitialize it.

## Define covers, script, and storyboard

- Match title wording to the target 平台 and audience. Keep it accurate and 不过度标题党. If the source cannot fit the duration, 压缩 to one coherent message or 拆成系列 instead of rushing every point.
- Prefer the user's authorized 人物, 产品, and 品牌素材 for covers. If these are insufficient, collect a 视觉参考 direction, then use ImageGen to create 原创 imagery rather than copying the reference.
- Check each of the three covers independently for 标题可读, UI 安全区, 人物和产品完整, and 与视频风格一致 before presenting them.
- Write script and storyboard as a 时间-coded plan. Include 旁白, 字幕, 画面, 素材来源 or 生成方式, 动效, and 音效 for every segment.
- Structure the timeline as hook, core, and CTA. Make the opening promise clear, develop one coherent core message, and end with an appropriate CTA.

## Manage state

- Run `python3 "$SKILL_ROOT/scripts/project_state.py" init "$PROJECT"` only for a new path.
- Append `--width W --height H --min-duration MIN --max-duration MAX` when the user explicitly overrides the default 1080x1920, 30–60 second specification.
- Run `python3 "$SKILL_ROOT/scripts/project_state.py" show "$PROJECT"` before every resumed operation so interrupted cover transactions recover.
- Advance only `title_pending` → `cover_pending` → `storyboard_pending` → `production_ready`.
- Preserve UTF-8 Chinese text and keep filenames stable.
- Stop after presenting each gated artifact unless explicit `--direct` applies.

## Record approvals

- Record the chosen title through `python3 "$SKILL_ROOT/scripts/project_state.py" approve-title "$PROJECT" --title "TITLE"`.
- Require all three cover files before `python3 "$SKILL_ROOT/scripts/project_state.py" select-cover "$PROJECT" --cover FILENAME`.
- Record script and storyboard approval through `python3 "$SKILL_ROOT/scripts/project_state.py" approve-storyboard "$PROJECT"`.
- Do not reinterpret feedback as approval when it requests another revision.
- Run `python3 "$SKILL_ROOT/scripts/project_state.py" direct "$PROJECT"` when the user explicitly changes an existing project to unattended completion. Record each generated automatic artifact with `record-artifact` before delivery.
- When any downstream generation, render, or QC step fails, 不得重生成已确认 title, cover, script, or storyboard. Repair only the failed downstream artifact, 除非用户主动要求 revise an approved artifact.
