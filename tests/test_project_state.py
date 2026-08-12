import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from scripts import project_state


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = REPO_ROOT / "assets" / "project-template"


class ProjectStateTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.project = self.root / "demo"

    def read_state(self):
        return json.loads(
            (self.project / "project-state.json").read_text(encoding="utf-8")
        )

    def make_covers(self):
        covers = self.project / "covers"
        covers.mkdir(exist_ok=True)
        for name in ("cover-a.png", "cover-b.png", "cover-c.png"):
            (covers / name).write_bytes(name.encode("utf-8"))

    def test_init_copies_template_and_creates_default_pending_state(self):
        project_state.initialize_project(self.project)

        state = self.read_state()
        self.assertEqual("title_pending", state["stage"])
        self.assertEqual(
            {
                "width": 1080,
                "height": 1920,
                "duration_min": 30,
                "duration_max": 60,
            },
            state["spec"],
        )
        self.assertFalse(state["direct"])
        self.assertEqual(
            {"title": None, "cover": None, "storyboard": None},
            state["confirmations"],
        )
        self.assertEqual(
            {
                "video": "output/final-vertical.mp4",
                "cover": "output/cover.png",
                "subtitles": "output/subtitles.srt",
                "report": "output/production-report.md",
                "edit_dir": "edit",
            },
            state["outputs"],
        )
        self.assertEqual(
            {
                "title": "title/candidates.md",
                "covers": "covers",
                "cover": "covers/selected.png",
                "script": "script/script.md",
                "storyboard": "script/storyboard.md",
            },
            state["artifacts"],
        )
        for relative_directory in (
            "input",
            "covers",
            "assets/generated",
            "assets/sourced",
            "assets/audio",
            "assets/fonts",
            "edit",
            "preview",
            "output",
        ):
            self.assertTrue((self.project / relative_directory).is_dir())
        for relative_path in (
            "brief.md",
            "title/candidates.md",
            "script/script.md",
            "script/storyboard.md",
            "output/production-report.md",
        ):
            self.assertEqual(
                (TEMPLATE_ROOT / relative_path).read_text(encoding="utf-8"),
                (self.project / relative_path).read_text(encoding="utf-8"),
            )

    def test_init_refuses_to_overwrite_an_existing_project(self):
        self.project.mkdir()
        marker = self.project / "keep.txt"
        marker.write_text("keep", encoding="utf-8")

        with self.assertRaisesRegex(project_state.ProjectStateError, "already exists"):
            project_state.initialize_project(self.project)

        self.assertEqual("keep", marker.read_text(encoding="utf-8"))
        self.assertFalse((self.project / "project-state.json").exists())

    def test_init_does_not_delete_a_directory_created_during_copy_race(self):
        marker = self.project / "concurrent-marker.txt"
        real_copytree = shutil.copytree

        def race_copytree(source, destination, *args, **kwargs):
            destination = Path(destination)
            destination.mkdir(parents=True, exist_ok=True)
            marker.write_text("concurrent", encoding="utf-8")
            if not kwargs.get("dirs_exist_ok", False):
                raise FileExistsError(destination)
            return real_copytree(source, destination, *args, **kwargs)

        with mock.patch("scripts.project_state.shutil.copytree", side_effect=race_copytree):
            try:
                project_state.initialize_project(self.project)
            except FileExistsError:
                pass

        self.assertEqual("concurrent", marker.read_text(encoding="utf-8"))

    def test_init_direct_is_ready_but_preserves_all_artifact_fields(self):
        project_state.initialize_project(self.project, direct=True)

        state = self.read_state()
        self.assertEqual("production_ready", state["stage"])
        self.assertTrue(state["direct"])
        self.assertEqual(
            {"title", "covers", "cover", "script", "storyboard"},
            set(state["artifacts"]),
        )
        self.assertEqual(
            {
                "title": "pending_auto",
                "covers": "pending_auto",
                "cover": "pending_auto",
                "script": "pending_auto",
                "storyboard": "pending_auto",
            },
            state["artifact_status"],
        )

    def test_init_accepts_valid_spec_overrides_and_rejects_invalid_ones(self):
        project_state.initialize_project(
            self.project,
            width=1920,
            height=1080,
            min_duration=10,
            max_duration=120,
        )
        self.assertEqual(
            {
                "width": 1920,
                "height": 1080,
                "duration_min": 10,
                "duration_max": 120,
            },
            self.read_state()["spec"],
        )
        for index, arguments in enumerate(
            (
                {"width": 0},
                {"height": -1},
                {"min_duration": 0},
                {"max_duration": 0},
                {"min_duration": 61, "max_duration": 60},
            )
        ):
            with self.subTest(arguments=arguments):
                with self.assertRaisesRegex(project_state.ProjectStateError, "spec"):
                    project_state.initialize_project(self.root / f"bad-{index}", **arguments)

    def test_title_approval_is_only_allowed_from_title_pending(self):
        project_state.initialize_project(self.project)
        project_state.approve_title(self.project, "AI 正在改变办公室工作")

        state = self.read_state()
        self.assertEqual("cover_pending", state["stage"])
        self.assertEqual("AI 正在改变办公室工作", state["title"])
        self.assertEqual("completed", state["artifact_status"]["title"])
        self.assertIsNotNone(state["confirmations"]["title"])
        datetime.fromisoformat(state["confirmations"]["title"].replace("Z", "+00:00"))
        with self.assertRaisesRegex(project_state.ProjectStateError, "title_pending"):
            project_state.approve_title(self.project, "另一个标题")

    def test_cover_selection_requires_all_three_candidates(self):
        project_state.initialize_project(self.project)
        project_state.approve_title(self.project, "标题")
        covers = self.project / "covers"
        covers.mkdir(exist_ok=True)
        (covers / "cover-a.png").write_bytes(b"a")
        (covers / "cover-b.png").write_bytes(b"b")

        with self.assertRaisesRegex(project_state.ProjectStateError, "cover-c.png"):
            project_state.select_cover(self.project, "cover-a.png")

        self.assertEqual("cover_pending", self.read_state()["stage"])

    def test_cover_selection_rejects_files_outside_the_three_candidates(self):
        project_state.initialize_project(self.project)
        project_state.approve_title(self.project, "标题")
        self.make_covers()

        with self.assertRaisesRegex(project_state.ProjectStateError, "cover-a.png"):
            project_state.select_cover(self.project, "other.png")

        self.assertFalse((self.project / "covers" / "selected.png").exists())

    def test_cover_selection_rejects_extra_image_candidates(self):
        project_state.initialize_project(self.project)
        project_state.approve_title(self.project, "标题")
        self.make_covers()
        covers = self.project / "covers"
        (covers / "notes.txt").write_text("辅助说明", encoding="utf-8")
        (covers / "cover-d.jpg").write_bytes(b"d")

        with self.assertRaisesRegex(project_state.ProjectStateError, "unexpected"):
            project_state.select_cover(self.project, "cover-a.png")

        self.assertEqual("cover_pending", self.read_state()["stage"])

    def test_existing_selected_output_is_not_treated_as_a_candidate(self):
        project_state.initialize_project(self.project)
        project_state.approve_title(self.project, "标题")
        self.make_covers()
        selected = self.project / "covers" / "selected.png"
        selected.write_bytes(b"old")

        project_state.select_cover(self.project, "cover-c.png")

        self.assertEqual(b"cover-c.png", selected.read_bytes())

    def test_cover_selection_copies_choice_and_advances_to_storyboard(self):
        project_state.initialize_project(self.project)
        project_state.approve_title(self.project, "标题")
        self.make_covers()

        project_state.select_cover(self.project, "cover-b.png")

        state = self.read_state()
        self.assertEqual("storyboard_pending", state["stage"])
        self.assertEqual("cover-b.png", state["selected_cover"])
        self.assertEqual("completed", state["artifact_status"]["covers"])
        self.assertEqual("completed", state["artifact_status"]["cover"])
        self.assertIsNotNone(state["confirmations"]["cover"])
        self.assertEqual(
            (self.project / "covers" / "cover-b.png").read_bytes(),
            (self.project / "covers" / "selected.png").read_bytes(),
        )

    def test_cover_selection_preserves_artifact_when_state_write_fails(self):
        project_state.initialize_project(self.project)
        project_state.approve_title(self.project, "标题")
        self.make_covers()
        selected = self.project / "covers" / "selected.png"
        selected.write_bytes(b"old-selected")

        with mock.patch(
            "scripts.project_state._write_state",
            side_effect=project_state.ProjectStateError("state write failed"),
        ):
            with self.assertRaisesRegex(project_state.ProjectStateError, "state write failed"):
                project_state.select_cover(self.project, "cover-b.png")

        self.assertEqual(b"old-selected", selected.read_bytes())
        self.assertEqual("cover_pending", self.read_state()["stage"])

    def test_cover_replace_failure_rolls_back_state_and_preserves_artifact(self):
        project_state.initialize_project(self.project)
        project_state.approve_title(self.project, "标题")
        self.make_covers()
        selected = self.project / "covers" / "selected.png"
        selected.write_bytes(b"old-selected")
        real_replace = os.replace

        def fail_cover_replace(source, destination):
            if Path(destination) == selected:
                raise OSError("cover replace failed")
            return real_replace(source, destination)

        with mock.patch(
            "scripts.project_state.os.replace", side_effect=fail_cover_replace
        ):
            with self.assertRaisesRegex(project_state.ProjectStateError, "cover replace failed"):
                project_state.select_cover(self.project, "cover-c.png")

        self.assertEqual(b"old-selected", selected.read_bytes())
        state = self.read_state()
        self.assertEqual("cover_pending", state["stage"])
        self.assertNotIn("selected_cover", state)

    def test_show_recovers_interrupted_cover_transaction(self):
        project_state.initialize_project(self.project)
        project_state.approve_title(self.project, "标题")
        self.make_covers()
        selected = self.project / "covers" / "selected.png"
        selected.write_bytes(b"old-selected")
        marker = self.project / ".cover-selection-transaction.json"
        real_replace = os.replace

        def interrupt_cover_replace(source, destination):
            if Path(destination) == selected:
                raise KeyboardInterrupt("simulated process interruption")
            return real_replace(source, destination)

        with mock.patch(
            "scripts.project_state.os.replace", side_effect=interrupt_cover_replace
        ):
            with self.assertRaises(KeyboardInterrupt):
                project_state.select_cover(self.project, "cover-b.png")

        self.assertTrue(marker.is_file())
        self.assertFalse((self.project / "covers" / marker.name).exists())
        self.assertEqual(b"old-selected", selected.read_bytes())

        recovered = project_state.show_project(self.project)

        self.assertEqual("storyboard_pending", recovered["stage"])
        self.assertEqual("cover-b.png", recovered["selected_cover"])
        self.assertEqual(b"cover-b.png", selected.read_bytes())
        self.assertFalse(marker.exists())

    def test_show_rejects_tampered_cover_transaction_without_touching_external_file(self):
        project_state.initialize_project(self.project)
        victim = self.root / "victim.txt"
        victim.write_text("do not delete", encoding="utf-8")
        marker = self.project / ".cover-selection-transaction.json"
        marker.write_text(
            json.dumps(
                {
                    "original_state": {"stage": "cover_pending"},
                    "target_cover": "../../victim.png",
                    "selected_existed": True,
                    "backup_path": "../victim.txt",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            project_state.ProjectStateError, "cover selection transaction"
        ):
            project_state.show_project(self.project)

        self.assertEqual("do not delete", victim.read_text(encoding="utf-8"))
        self.assertTrue(marker.is_file())

    def test_storyboard_approval_is_only_allowed_after_cover_selection(self):
        project_state.initialize_project(self.project)
        with self.assertRaisesRegex(project_state.ProjectStateError, "storyboard_pending"):
            project_state.approve_storyboard(self.project)

        project_state.approve_title(self.project, "标题")
        self.make_covers()
        project_state.select_cover(self.project, "cover-c.png")
        project_state.approve_storyboard(self.project)
        state = self.read_state()
        self.assertEqual("production_ready", state["stage"])
        self.assertEqual("completed", state["artifact_status"]["script"])
        self.assertEqual("completed", state["artifact_status"]["storyboard"])
        self.assertIsNotNone(state["confirmations"]["storyboard"])

    def test_direct_existing_project_preserves_completed_and_marks_rest_pending_auto(self):
        project_state.initialize_project(self.project)
        project_state.approve_title(self.project, "已确认标题")

        state = project_state.enable_direct(self.project)

        self.assertTrue(state["direct"])
        self.assertEqual("production_ready", state["stage"])
        self.assertEqual("completed", state["artifact_status"]["title"])
        for name in ("covers", "cover", "script", "storyboard"):
            self.assertEqual("pending_auto", state["artifact_status"][name])

    def test_direct_project_can_record_existing_automatic_artifacts(self):
        project_state.initialize_project(self.project, direct=True)
        title_path = self.project / "title" / "candidates.md"
        project_state.record_artifact(
            self.project, "title", title_path, value="自动标题"
        )
        self.make_covers()
        project_state.record_artifact(self.project, "covers", self.project / "covers")
        selected = self.project / "covers" / "selected.png"
        selected.write_bytes((self.project / "covers" / "cover-a.png").read_bytes())
        project_state.record_artifact(
            self.project, "cover", selected, value="cover-a.png"
        )
        for name, relative_path in (
            ("script", "script/script.md"),
            ("storyboard", "script/storyboard.md"),
        ):
            (self.project / relative_path).write_text(
                f"# {name}\n\n自动生成的完整内容\n", encoding="utf-8"
            )
            project_state.record_artifact(
                self.project, name, self.project / relative_path
            )

        state = self.read_state()
        for name in ("title", "covers", "cover", "script", "storyboard"):
            self.assertEqual("completed", state["artifact_status"][name])
            self.assertIn("path", state["artifact_records"][name])
        self.assertEqual("自动标题", state["artifact_records"]["title"]["value"])
        self.assertEqual("cover-a.png", state["selected_cover"])

    def test_record_artifact_requires_direct_and_valid_existing_path(self):
        project_state.initialize_project(self.project)
        with self.assertRaisesRegex(project_state.ProjectStateError, "direct"):
            project_state.record_artifact(
                self.project, "title", self.project / "title/candidates.md"
            )

        project_state.enable_direct(self.project)
        with self.assertRaisesRegex(project_state.ProjectStateError, "exist"):
            project_state.record_artifact(
                self.project, "script", self.project / "missing.md"
            )

    def test_record_cover_uses_explicit_value_for_selected_cover(self):
        project_state.initialize_project(self.project, direct=True)
        selected = self.project / "covers" / "selected.png"
        self.make_covers()
        selected.write_bytes(b"cover-b.png")

        state = project_state.record_artifact(
            self.project, "cover", selected, value="cover-b.png"
        )

        self.assertEqual("cover-b.png", state["selected_cover"])
        self.assertEqual("cover-b.png", state["artifact_records"]["cover"]["value"])

    def test_record_artifact_requires_canonical_project_paths(self):
        project_state.initialize_project(self.project, direct=True)
        alternate = self.project / "input" / "alternate.md"
        alternate.write_text("content", encoding="utf-8")
        for name in ("title", "script", "storyboard"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(project_state.ProjectStateError, "canonical"):
                    project_state.record_artifact(self.project, name, alternate)
        other_covers = self.project / "input" / "covers"
        other_covers.mkdir()
        for filename in ("cover-a.png", "cover-b.png", "cover-c.png"):
            (other_covers / filename).write_bytes(filename.encode("utf-8"))
        with self.assertRaisesRegex(project_state.ProjectStateError, "canonical"):
            project_state.record_artifact(self.project, "covers", other_covers)

    def test_record_cover_requires_valid_candidate_value_and_matching_bytes(self):
        project_state.initialize_project(self.project, direct=True)
        self.make_covers()
        selected = self.project / "covers" / "selected.png"
        selected.write_bytes(b"cover-a.png")
        for value in (None, "selected.png", "cover-d.png", "../../outside.png"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(project_state.ProjectStateError, "cover"):
                    project_state.record_artifact(
                        self.project, "cover", selected, value=value
                    )
        with self.assertRaisesRegex(project_state.ProjectStateError, "match"):
            project_state.record_artifact(
                self.project, "cover", selected, value="cover-b.png"
            )

    def test_record_title_requires_nonempty_value_and_updates_state(self):
        project_state.initialize_project(self.project, direct=True)
        title_path = self.project / "title/candidates.md"
        title_path.write_text("最终标题", encoding="utf-8")
        for value in (None, "", "   "):
            with self.subTest(value=value):
                with self.assertRaisesRegex(project_state.ProjectStateError, "title"):
                    project_state.record_artifact(
                        self.project, "title", title_path, value=value
                    )
        state = project_state.record_artifact(
            self.project, "title", title_path, value="  最终标题  "
        )
        self.assertEqual("最终标题", state["title"])
        self.assertEqual("最终标题", state["artifact_records"]["title"]["value"])

    def test_record_script_and_storyboard_reject_untouched_templates(self):
        project_state.initialize_project(self.project, direct=True)
        for name, relative in (
            ("script", "script/script.md"),
            ("storyboard", "script/storyboard.md"),
        ):
            path = self.project / relative
            with self.subTest(name=name):
                with self.assertRaisesRegex(project_state.ProjectStateError, "template"):
                    project_state.record_artifact(self.project, name, path)
                path.write_text(f"# {name}\n\n完成内容\n", encoding="utf-8")
                state = project_state.record_artifact(self.project, name, path)
                self.assertEqual("completed", state["artifact_status"][name])

    def test_state_updates_use_atomic_replace(self):
        project_state.initialize_project(self.project)

        with mock.patch("scripts.project_state.os.replace", wraps=project_state.os.replace) as replace:
            project_state.approve_title(self.project, "标题")

        replace.assert_called_once()
        temporary_path, destination = replace.call_args.args
        self.assertEqual(self.project / "project-state.json", Path(destination))
        self.assertNotEqual(Path(temporary_path), Path(destination))

    def test_cli_supports_init_transitions_and_show(self):
        def run(*arguments):
            return subprocess.run(
                [sys.executable, "-m", "scripts.project_state", *map(str, arguments)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(0, run("init", self.project).returncode)
        self.assertEqual(
            0,
            run("approve-title", self.project, "--title", "CLI 标题").returncode,
        )
        self.make_covers()
        self.assertEqual(
            0,
            run("select-cover", self.project, "--cover", "cover-a.png").returncode,
        )
        self.assertEqual(0, run("approve-storyboard", self.project).returncode)
        shown = run("show", self.project)
        self.assertEqual(0, shown.returncode, shown.stderr)
        self.assertEqual("production_ready", json.loads(shown.stdout)["stage"])

    def test_cli_supports_spec_override_direct_and_artifact_recording(self):
        def run(*arguments):
            return subprocess.run(
                [sys.executable, "-m", "scripts.project_state", *map(str, arguments)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        initialized = run(
            "init",
            self.project,
            "--width",
            "1920",
            "--height",
            "1080",
            "--min-duration",
            "15",
            "--max-duration",
            "90",
        )
        self.assertEqual(0, initialized.returncode, initialized.stderr)
        self.assertEqual(1920, json.loads(initialized.stdout)["spec"]["width"])
        direct = run("direct", self.project)
        self.assertEqual(0, direct.returncode, direct.stderr)
        recorded = run(
            "record-artifact",
            self.project,
            "--name",
            "title",
            "--path",
            self.project / "title/candidates.md",
            "--value",
            "自动标题",
        )
        self.assertEqual(0, recorded.returncode, recorded.stderr)
        state = json.loads(recorded.stdout)
        self.assertEqual("completed", state["artifact_status"]["title"])
        self.assertEqual("自动标题", state["artifact_records"]["title"]["value"])


if __name__ == "__main__":
    unittest.main()
