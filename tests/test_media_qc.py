import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import media_qc


REPO_ROOT = Path(__file__).resolve().parents[1]


def valid_probe_fixture():
    return {
        "format": {"duration": "45.25", "format_name": "mov,mp4,m4a,3gp,3g2,mj2"},
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1080,
                "height": 1920,
            },
            {"codec_type": "audio", "codec_name": "aac"},
        ],
    }


class MediaQCTests(unittest.TestCase):
    def test_accepts_readable_h264_vertical_video_with_audio_in_range(self):
        result = media_qc.evaluate_probe(valid_probe_fixture())

        self.assertTrue(result["passed"])
        self.assertEqual([], result["failures"])
        self.assertEqual(
            {
                "codec": "h264",
                "width": 1080,
                "height": 1920,
                "duration": 45.25,
                "has_audio": True,
                "container": "mov,mp4,m4a,3gp,3g2,mj2",
            },
            result["measurements"],
        )
        self.assertNotIn("quality", json.dumps(result).lower())

    def test_rejects_landscape_video_with_clear_failure(self):
        probe = valid_probe_fixture()
        probe["streams"][0].update(width=1920, height=1080)

        result = media_qc.evaluate_probe(probe)

        self.assertFalse(result["passed"])
        self.assertTrue(any("1080x1920" in failure for failure in result["failures"]))

    def test_rejects_missing_audio(self):
        probe = valid_probe_fixture()
        probe["streams"] = [probe["streams"][0]]

        result = media_qc.evaluate_probe(probe)

        self.assertFalse(result["passed"])
        self.assertIn("audio", " ".join(result["failures"]).lower())

    def test_rejects_duration_outside_inclusive_range(self):
        for duration in ("29.99", "60.01"):
            with self.subTest(duration=duration):
                probe = valid_probe_fixture()
                probe["format"]["duration"] = duration
                result = media_qc.evaluate_probe(probe)
                self.assertFalse(result["passed"])
                self.assertIn("30", " ".join(result["failures"]))
                self.assertIn("60", " ".join(result["failures"]))

    def test_rejects_non_finite_duration_values(self):
        for duration in ("nan", "inf", "-inf"):
            with self.subTest(duration=duration):
                probe = valid_probe_fixture()
                probe["format"]["duration"] = duration

                result = media_qc.evaluate_probe(probe)

                self.assertFalse(result["passed"])
                self.assertIsNone(result["measurements"]["duration"])
                self.assertIn("duration", " ".join(result["failures"]).lower())

    def test_rejects_non_h264_video(self):
        probe = valid_probe_fixture()
        probe["streams"][0]["codec_name"] = "hevc"

        result = media_qc.evaluate_probe(probe)

        self.assertFalse(result["passed"])
        self.assertIn("h264", " ".join(result["failures"]).lower())

    def test_rejects_non_mp4_container(self):
        probe = valid_probe_fixture()
        probe["format"]["format_name"] = "matroska,webm"

        result = media_qc.evaluate_probe(probe)

        self.assertFalse(result["passed"])
        self.assertEqual("matroska,webm", result["measurements"]["container"])
        self.assertIn("mp4", " ".join(result["failures"]).lower())

    def test_malformed_probe_data_returns_clear_failures(self):
        result = media_qc.evaluate_probe({"streams": "invalid", "format": {}})

        self.assertFalse(result["passed"])
        self.assertTrue(result["failures"])
        self.assertIsNone(result["measurements"]["duration"])

    def test_probe_uses_explicit_argv_timeout_and_no_shell(self):
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(valid_probe_fixture()), stderr=""
        )
        with mock.patch("scripts.media_qc.subprocess.run", return_value=completed) as run:
            result = media_qc.probe_media(Path("video.mp4"), timeout=7)

        self.assertEqual(valid_probe_fixture(), result)
        arguments, keywords = run.call_args
        self.assertEqual("ffprobe", arguments[0][0])
        self.assertIn("video.mp4", arguments[0])
        self.assertEqual(7, keywords["timeout"])
        self.assertFalse(keywords.get("shell", False))

    def test_nonzero_ffprobe_exit_is_reported_as_failed_qc(self):
        completed = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Invalid data found"
        )
        with mock.patch("scripts.media_qc.subprocess.run", return_value=completed):
            result = media_qc.check_media(Path("broken.mp4"))

        self.assertFalse(result["passed"])
        self.assertIn("ffprobe", " ".join(result["failures"]).lower())
        self.assertIn("Invalid data found", " ".join(result["failures"]))

    def test_cli_json_supports_custom_thresholds(self):
        probe = valid_probe_fixture()
        probe["streams"][0].update(width=720, height=1280)
        probe["format"]["duration"] = "12"
        with tempfile.TemporaryDirectory() as temporary_directory:
            media_file = Path(temporary_directory) / "clip.mp4"
            media_file.write_bytes(b"fixture")
            completed = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(probe), stderr=""
            )
            with mock.patch("scripts.media_qc.subprocess.run", return_value=completed):
                stdout = sys.stdout
                try:
                    from io import StringIO

                    capture = StringIO()
                    sys.stdout = capture
                    exit_code = media_qc.main(
                        [
                            str(media_file),
                            "--json",
                            "--width",
                            "720",
                            "--height",
                            "1280",
                            "--min-duration",
                            "10",
                            "--max-duration",
                            "15",
                        ]
                    )
                finally:
                    sys.stdout = stdout

        self.assertEqual(0, exit_code)
        self.assertTrue(json.loads(capture.getvalue())["passed"])

    def test_evaluate_rejects_invalid_policy_bounds_with_clear_error(self):
        invalid_policies = (
            {"width": 0},
            {"height": -1},
            {"width": 1080.5},
            {"min_duration": -1},
            {"max_duration": float("inf")},
            {"min_duration": 61, "max_duration": 60},
        )
        for policy in invalid_policies:
            with self.subTest(policy=policy):
                with self.assertRaisesRegex(ValueError, "policy"):
                    media_qc.evaluate_probe(valid_probe_fixture(), **policy)

    def test_cli_rejects_invalid_policy_with_nonzero_exit(self):
        for arguments in (
            ["video.mp4", "--width", "0"],
            ["video.mp4", "--height", "-1"],
            ["video.mp4", "--min-duration", "nan"],
            ["video.mp4", "--max-duration", "inf"],
            ["video.mp4", "--min-duration", "61", "--max-duration", "60"],
        ):
            with self.subTest(arguments=arguments):
                with mock.patch("sys.stderr"):
                    exit_code = media_qc.main(arguments)
                self.assertNotEqual(0, exit_code)


if __name__ == "__main__":
    unittest.main()
