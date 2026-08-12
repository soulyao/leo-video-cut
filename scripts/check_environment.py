"""Report local video-production dependencies without inspecting secrets."""

import argparse
import json
import shutil
import subprocess


DEPENDENCIES = (
    "ffmpeg",
    "ffprobe",
    "python3",
    "node",
    "npx",
    "whisper",
    "local_tts",
    "hyperframes",
)
REQUIRED = {"ffmpeg", "ffprobe"}

LOCAL_GUIDANCE = {
    "ffmpeg": (
        "Install FFmpeg locally with `brew install ffmpeg`; this also provides "
        "the required ffmpeg executable."
    ),
    "ffprobe": (
        "Install FFmpeg locally with `brew install ffmpeg`; this also provides "
        "the required ffprobe executable."
    ),
    "python3": (
        "Install Python locally with `xcode-select --install` for the macOS "
        "Command Line Tools, or use `brew install python`."
    ),
    "node": (
        "Install Node.js locally with `brew install node`; this provides node "
        "and npx."
    ),
    "npx": (
        "Install Node.js locally with `brew install node`; this provides node "
        "and npx."
    ),
    "whisper": (
        "Install a local Whisper CLI (for example whisper.cpp or the local "
        "openai-whisper package) and place `whisper` on PATH."
    ),
    "local_tts": (
        "On macOS use the built-in local `say` command; otherwise install a "
        "local offline TTS engine and place its command on PATH."
    ),
    "hyperframes": (
        "Install HyperFrames locally so `hyperframes` is on PATH, or install it "
        "in the local Node project for `npx hyperframes` use with --probe."
    ),
}


def _default_version_runner(command):
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    output = (completed.stdout or completed.stderr).strip()
    if completed.returncode != 0:
        return None
    return output or "version command succeeded"


def _result(available, required, detail):
    return {
        "available": bool(available),
        "required": bool(required),
        "detail": detail,
    }


def _probe_version(version_runner, command):
    try:
        return version_runner(command)
    except (OSError, subprocess.SubprocessError):
        return None


def check_environment(lookup=shutil.which, version_runner=None, probe=False):
    """Return dependency availability using injectable local-only operations."""
    version_runner = version_runner or _default_version_runner
    paths = {
        name: lookup(name)
        for name in ("ffmpeg", "ffprobe", "python3", "node", "npx", "whisper")
    }
    paths["hyperframes"] = lookup("hyperframes")
    say_path = lookup("say")

    report = {}
    for name in ("ffmpeg", "ffprobe", "python3", "node", "npx", "whisper"):
        path = paths[name]
        detail = (
            f"Found local executable: {path}" if path else LOCAL_GUIDANCE[name]
        )
        if probe and path:
            version = _probe_version(version_runner, [path, "--version"])
            if version:
                detail = version
        report[name] = _result(path, name in REQUIRED, detail)

    if say_path:
        tts_detail = f"Found macOS local TTS: {say_path}"
        if probe:
            version = _probe_version(version_runner, [say_path, "--version"])
            if version:
                tts_detail = version
        report["local_tts"] = _result(True, False, tts_detail)
    else:
        report["local_tts"] = _result(False, False, LOCAL_GUIDANCE["local_tts"])

    hyperframes_path = paths["hyperframes"]
    hyperframes_detail = (
        f"Found local executable: {hyperframes_path}"
        if hyperframes_path
        else LOCAL_GUIDANCE["hyperframes"]
    )
    hyperframes_available = bool(hyperframes_path)
    if probe and hyperframes_path:
        version = _probe_version(version_runner, [hyperframes_path, "--version"])
        if version:
            hyperframes_detail = version
    elif probe and paths["npx"]:
        version = _probe_version(
            version_runner,
            [paths["npx"], "--no-install", "hyperframes", "--version"],
        )
        if version:
            hyperframes_available = True
            hyperframes_detail = version
    report["hyperframes"] = _result(
        hyperframes_available, False, hyperframes_detail
    )

    return {name: report[name] for name in DEPENDENCIES}


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument(
        "--probe",
        action="store_true",
        help="run local version commands, including the HyperFrames npx probe",
    )
    return parser


def main(argv=None):
    arguments = _parser().parse_args(argv)
    report = check_environment(probe=arguments.probe)
    if arguments.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for name, result in report.items():
            status = "available" if result["available"] else "missing"
            required = "required" if result["required"] else "optional"
            print(f"{name}: {status} ({required}) — {result['detail']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
