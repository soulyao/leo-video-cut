import json
import subprocess
import sys
import unittest
from pathlib import Path

from scripts import check_environment


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_DEPENDENCIES = {
    "ffmpeg",
    "ffprobe",
    "python3",
    "node",
    "npx",
    "whisper",
    "local_tts",
    "hyperframes",
}


class CheckEnvironmentTests(unittest.TestCase):
    def test_report_has_complete_schema_and_required_flags(self):
        paths = {
            "ffmpeg": "/tools/ffmpeg",
            "ffprobe": "/tools/ffprobe",
            "python3": "/tools/python3",
            "node": "/tools/node",
            "npx": "/tools/npx",
            "whisper": "/tools/whisper",
            "say": "/usr/bin/say",
            "hyperframes": "/tools/hyperframes",
        }

        report = check_environment.check_environment(lookup=paths.get)

        self.assertEqual(EXPECTED_DEPENDENCIES, set(report))
        for name, result in report.items():
            self.assertEqual({"available", "required", "detail"}, set(result), name)
            self.assertIsInstance(result["available"], bool)
            self.assertIsInstance(result["required"], bool)
            self.assertIsInstance(result["detail"], str)
        self.assertTrue(report["ffmpeg"]["required"])
        self.assertTrue(report["ffprobe"]["required"])
        for optional in EXPECTED_DEPENDENCIES - {"ffmpeg", "ffprobe"}:
            self.assertFalse(report[optional]["required"], optional)
        self.assertTrue(report["local_tts"]["available"])

    def test_missing_optional_tools_have_local_actionable_guidance(self):
        report = check_environment.check_environment(lookup=lambda _name: None)

        for name in ("whisper", "local_tts", "hyperframes"):
            detail = report[name]["detail"].lower()
            self.assertFalse(report[name]["available"])
            self.assertIn("local", detail)
            self.assertNotIn("api", detail)
        self.assertIn("whisper", report["whisper"]["detail"].lower())
        self.assertIn("say", report["local_tts"]["detail"].lower())
        self.assertIn("hyperframes", report["hyperframes"]["detail"].lower())

    def test_all_missing_dependencies_have_actionable_local_install_guidance(self):
        report = check_environment.check_environment(lookup=lambda _name: None)

        self.assertIn("brew install ffmpeg", report["ffmpeg"]["detail"].lower())
        self.assertIn("brew install ffmpeg", report["ffprobe"]["detail"].lower())
        python_detail = report["python3"]["detail"].lower()
        self.assertTrue(
            "xcode-select" in python_detail or "brew install python" in python_detail
        )
        self.assertIn("brew install node", report["node"]["detail"].lower())
        self.assertIn("brew install node", report["npx"]["detail"].lower())
        for name, result in report.items():
            self.assertIn("local", result["detail"].lower(), name)
            self.assertNotIn("api", result["detail"].lower(), name)

    def test_default_check_does_not_run_version_commands(self):
        commands = []

        def runner(command):
            commands.append(command)
            return "version"

        check_environment.check_environment(
            lookup=lambda name: f"/tools/{name}",
            version_runner=runner,
        )

        self.assertEqual([], commands)

    def test_probe_runs_local_versions_and_npx_hyperframes_probe(self):
        commands = []

        def lookup(name):
            if name == "hyperframes":
                return None
            return f"/tools/{name}"

        def runner(command):
            commands.append(command)
            if command == [
                "/tools/npx",
                "--no-install",
                "hyperframes",
                "--version",
            ]:
                return "HyperFrames 1.2.3"
            return "tool 1.0"

        report = check_environment.check_environment(
            lookup=lookup,
            version_runner=runner,
            probe=True,
        )

        self.assertIn(
            ["/tools/npx", "--no-install", "hyperframes", "--version"],
            commands,
        )
        self.assertTrue(report["hyperframes"]["available"])
        self.assertIn("1.2.3", report["hyperframes"]["detail"])

    def test_probe_keeps_hyperframes_missing_when_local_npx_package_is_absent(self):
        def lookup(name):
            if name == "hyperframes":
                return None
            return f"/tools/{name}"

        def runner(command):
            if command == [
                "/tools/npx",
                "--no-install",
                "hyperframes",
                "--version",
            ]:
                return None
            return "tool 1.0"

        report = check_environment.check_environment(
            lookup=lookup,
            version_runner=runner,
            probe=True,
        )

        self.assertFalse(report["hyperframes"]["available"])

    def test_cli_json_emits_machine_readable_report(self):
        completed = subprocess.run(
            [sys.executable, "scripts/check_environment.py", "--json"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(EXPECTED_DEPENDENCIES, set(report))


if __name__ == "__main__":
    unittest.main()
