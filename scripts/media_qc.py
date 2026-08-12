"""Check objective final-media properties reported by ffprobe."""

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path


class ProbeError(Exception):
    """Raised when ffprobe cannot return readable JSON metadata."""


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _validate_policy(width, height, min_duration, max_duration):
    if (
        isinstance(width, bool)
        or not isinstance(width, int)
        or width <= 0
        or isinstance(height, bool)
        or not isinstance(height, int)
        or height <= 0
    ):
        raise ValueError("QC policy width and height must be positive integers")
    durations = (min_duration, max_duration)
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
        for value in durations
    ):
        raise ValueError("QC policy duration bounds must be finite and nonnegative")
    if min_duration > max_duration:
        raise ValueError("QC policy min_duration must not exceed max_duration")


def evaluate_probe(
    probe,
    width=1080,
    height=1920,
    min_duration=30,
    max_duration=60,
):
    """Evaluate objective stream metadata without judging perceptual content."""
    _validate_policy(width, height, min_duration, max_duration)
    failures = []
    streams = probe.get("streams") if isinstance(probe, dict) else None
    if not isinstance(streams, list):
        streams = []
        failures.append("Malformed ffprobe data: streams must be a list.")

    video_streams = [
        stream
        for stream in streams
        if isinstance(stream, dict) and stream.get("codec_type") == "video"
    ]
    audio_streams = [
        stream
        for stream in streams
        if isinstance(stream, dict) and stream.get("codec_type") == "audio"
    ]
    video = video_streams[0] if video_streams else {}
    if not video_streams:
        failures.append("No readable video stream was reported by ffprobe.")

    codec = video.get("codec_name")
    measured_width = video.get("width")
    measured_height = video.get("height")
    format_data = probe.get("format", {}) if isinstance(probe, dict) else {}
    if not isinstance(format_data, dict):
        format_data = {}
        failures.append("Malformed ffprobe data: format must be an object.")
    duration = _number(format_data.get("duration"))
    container = format_data.get("format_name")

    if codec != "h264":
        failures.append(f"Video codec must be h264; measured {codec!r}.")
    container_names = (
        {name.strip().lower() for name in container.split(",")}
        if isinstance(container, str)
        else set()
    )
    if "mp4" not in container_names:
        failures.append(f"Video container must include mp4; measured {container!r}.")
    if measured_width != width or measured_height != height:
        failures.append(
            f"Video dimensions must be {width}x{height}; measured "
            f"{measured_width}x{measured_height}."
        )
    if duration is None:
        failures.append("Video duration is missing or malformed.")
    elif duration < min_duration or duration > max_duration:
        failures.append(
            f"Video duration must be between {min_duration} and {max_duration} "
            f"seconds; measured {duration:.3f} seconds."
        )
    if not audio_streams:
        failures.append("At least one audio stream is required; measured none.")

    return {
        "passed": not failures,
        "measurements": {
            "codec": codec,
            "width": measured_width,
            "height": measured_height,
            "duration": duration,
            "has_audio": bool(audio_streams),
            "container": container,
        },
        "failures": failures,
    }


def probe_media(media_file, timeout=20):
    """Run ffprobe with explicit argv and parse its JSON response."""
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        str(media_file),
    ]
    try:
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ProbeError(f"ffprobe could not run: {error}") from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "unknown ffprobe error"
        raise ProbeError(f"ffprobe failed: {detail}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ProbeError(f"ffprobe returned malformed JSON: {error}") from error


def check_media(media_file, **thresholds):
    try:
        probe = probe_media(media_file)
    except ProbeError as error:
        return {
            "passed": False,
            "measurements": {
                "codec": None,
                "width": None,
                "height": None,
                "duration": None,
                "has_audio": False,
                "container": None,
            },
            "failures": [str(error)],
        }
    return evaluate_probe(probe, **thresholds)


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--min-duration", type=float, default=30)
    parser.add_argument("--max-duration", type=float, default=60)
    return parser


def main(argv=None):
    arguments = _parser().parse_args(argv)
    try:
        _validate_policy(
            arguments.width,
            arguments.height,
            arguments.min_duration,
            arguments.max_duration,
        )
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    result = check_media(
        arguments.file,
        width=arguments.width,
        height=arguments.height,
        min_duration=arguments.min_duration,
        max_duration=arguments.max_duration,
    )
    if arguments.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        measurements = result["measurements"]
        print(
            "Measurements: "
            f"codec={measurements['codec']}, "
            f"size={measurements['width']}x{measurements['height']}, "
            f"duration={measurements['duration']}, "
            f"audio={measurements['has_audio']}"
            f", container={measurements['container']}"
        )
        for failure in result["failures"]:
            print(f"FAIL: {failure}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
