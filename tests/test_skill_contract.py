import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "SKILL.md"


def parse_skill():
    content = SKILL_PATH.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n(.*)\Z", content, re.DOTALL)
    if not match:
        raise AssertionError("SKILL.md must have YAML frontmatter")
    frontmatter = {}
    for line in match.group(1).splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            raise AssertionError(f"invalid frontmatter line: {line}")
        frontmatter[key.strip()] = value.strip().strip('"')
    return frontmatter, match.group(2)


class SkillContractTests(unittest.TestCase):
    def test_frontmatter_contract(self):
        frontmatter, _body = parse_skill()

        self.assertEqual({"name", "description"}, set(frontmatter))
        self.assertEqual("leo-video-cut", frontmatter["name"])
        self.assertTrue(frontmatter["description"].startswith("Use when"))

    def test_body_contains_required_tools_values_and_commands(self):
        _frontmatter, body = parse_skill()

        for required in (
            "approve-title",
            "select-cover",
            "approve-storyboard",
            "three",
            "ImageGen",
            "1080",
            "1920",
            "30",
            "60",
            "direct",
            "HyperFrames",
            "FFmpeg",
            "Whisper",
        ):
            with self.subTest(required=required):
                self.assertIn(required, body)

    def test_body_defines_three_ordered_hard_gates(self):
        _frontmatter, body = parse_skill()
        title = body.index("approve-title")
        cover = body.index("select-cover")
        storyboard = body.index("approve-storyboard")

        self.assertLess(title, cover)
        self.assertLess(cover, storyboard)
        self.assertRegex(body.lower(), r"hard gate")
        self.assertGreaterEqual(body.lower().count("stop"), 3)

    def test_direct_is_the_only_explicit_pause_bypass(self):
        _frontmatter, body = parse_skill()

        self.assertIn("explicit `--direct`", body)
        self.assertIn("only pause bypass", body)
        self.assertIn("pending_auto", body)

    def test_body_limits_repairs_and_links_references_directly(self):
        _frontmatter, body = parse_skill()

        self.assertIn("3 repair rounds", body)
        for reference in (
            "references/workflow.md",
            "references/local-production.md",
            "references/quality.md",
        ):
            with self.subTest(reference=reference):
                self.assertIn(f"]({reference})", body)
                self.assertTrue((REPO_ROOT / reference).is_file())

    def test_commands_resolve_bundled_scripts_from_absolute_skill_root(self):
        _frontmatter, body = parse_skill()

        self.assertIn("SKILL_ROOT", body)
        self.assertIn("current SKILL.md", body)
        self.assertIn("absolute path", body)
        for script in (
            "check_environment.py",
            "project_state.py",
            "media_qc.py",
        ):
            with self.subTest(script=script):
                self.assertIn(f'python3 "$SKILL_ROOT/scripts/{script}"', body)

    def test_project_is_an_absolute_user_workspace_path_not_skill_storage(self):
        _frontmatter, body = parse_skill()

        self.assertIn("PROJECT", body)
        self.assertIn("user workspace", body)
        self.assertIn("absolute project path", body)
        self.assertIn("Never create PROJECT inside SKILL_ROOT", body)

    def test_implicit_urgency_does_not_bypass_approval_gates(self):
        _frontmatter, body = parse_skill()

        for phrase in ("赶时间", "你自己决定", "少问问题"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, body)
        self.assertIn("do not count as direct", body)

    def test_direct_mode_still_requires_exactly_three_cover_artifacts(self):
        _frontmatter, body = parse_skill()

        self.assertIn(
            "direct mode must still generate exactly three covers", body.lower()
        )
        self.assertIn("cover-a.png", body)
        self.assertIn("cover-b.png", body)
        self.assertIn("cover-c.png", body)

    def test_workflow_documents_spec_overrides_direct_and_delivery_paths(self):
        _frontmatter, body = parse_skill()

        for required in (
            "--width",
            "--height",
            "--min-duration",
            "--max-duration",
            "project_state.py\" direct",
            "record-artifact",
            "output/final-vertical.mp4",
            "output/cover.png",
            "output/subtitles.srt",
        ):
            with self.subTest(required=required):
                self.assertIn(required, body)

    def test_media_qc_command_matches_all_project_state_spec_values_without_jq(self):
        _frontmatter, body = parse_skill()

        self.assertIn('show "$PROJECT" > "$PROJECT/preview/project-state.json"', body)
        self.assertIn("match project-state spec", body)
        for flag in ("--width", "--height", "--min-duration", "--max-duration"):
            with self.subTest(flag=flag):
                self.assertIn(flag, body)
        self.assertNotRegex(body, r"(?m)^\s*jq\b|`jq\b")

    def test_production_report_uses_state_placeholders_and_requires_resolution(self):
        report = (REPO_ROOT / "assets/project-template/output/production-report.md").read_text(
            encoding="utf-8"
        )
        quality = (REPO_ROOT / "references/quality.md").read_text(encoding="utf-8")

        self.assertIn("<from project-state.json spec.width>", report)
        self.assertIn("<from project-state.json spec.height>", report)
        self.assertIn("replace", quality.lower())
        self.assertIn("no `<from project-state.json", quality)


if __name__ == "__main__":
    unittest.main()
