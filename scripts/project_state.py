"""Create and advance gated Leo Video Cut project state."""

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


STATE_FILE = "project-state.json"
TRANSACTION_FILE = ".cover-selection-transaction.json"
SELECTED_BACKUP_FILE = ".cover-selection-selected.backup"
TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "assets" / "project-template"
COVER_CANDIDATES = ("cover-a.png", "cover-b.png", "cover-c.png")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
ARTIFACT_NAMES = ("title", "covers", "cover", "script", "storyboard")


class ProjectStateError(Exception):
    """Raised when a project operation violates the workflow."""


def _state_path(project):
    return Path(project) / STATE_FILE


def _read_json(path, label):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProjectStateError(f"cannot read {label}: {error}") from error


def _load_state(project):
    path = _state_path(project)
    if not path.is_file():
        raise ProjectStateError(f"project state does not exist: {path}")
    state = _read_json(path, "project state")
    marker_path = Path(project) / TRANSACTION_FILE
    if marker_path.is_file():
        state = _recover_cover_transaction(Path(project), state, marker_path)
    return state


def _atomic_write_json(destination, value, label):
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            json.dump(value, temporary, ensure_ascii=False, indent=2)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, destination)
    except OSError as error:
        raise ProjectStateError(f"cannot write {label}: {error}") from error
    finally:
        if temporary_name:
            try:
                Path(temporary_name).unlink()
            except FileNotFoundError:
                pass


def _write_state(project, state):
    _atomic_write_json(_state_path(project), state, "project state")


def _atomic_replace_file(source, destination):
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            with Path(source).open("rb") as input_file:
                shutil.copyfileobj(input_file, temporary)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, destination)
        temporary_name = None
    except OSError as error:
        raise ProjectStateError(f"cannot replace {destination.name}: {error}") from error
    finally:
        if temporary_name:
            try:
                Path(temporary_name).unlink()
            except FileNotFoundError:
                pass


def _cleanup_cover_transaction(marker_path, backup_path):
    marker_path.unlink(missing_ok=True)
    backup_path.unlink(missing_ok=True)


def _restore_cover_transaction(project, transaction, marker_path):
    selected = project / "covers" / "selected.png"
    backup = project / SELECTED_BACKUP_FILE
    _write_state(project, transaction["original_state"])
    if transaction["selected_existed"]:
        _atomic_replace_file(backup, selected)
    else:
        selected.unlink(missing_ok=True)
    _cleanup_cover_transaction(marker_path, backup)
    return transaction["original_state"]


def _validate_cover_transaction(transaction):
    if not isinstance(transaction, dict):
        raise ProjectStateError("invalid cover selection transaction: expected object")
    if transaction.get("target_cover") not in COVER_CANDIDATES:
        raise ProjectStateError("invalid cover selection transaction: invalid target_cover")
    if transaction.get("backup_path") != SELECTED_BACKUP_FILE:
        raise ProjectStateError("invalid cover selection transaction: invalid backup_path")
    if not isinstance(transaction.get("selected_existed"), bool):
        raise ProjectStateError(
            "invalid cover selection transaction: invalid selected_existed"
        )
    original_state = transaction.get("original_state")
    if not isinstance(original_state, dict):
        raise ProjectStateError(
            "invalid cover selection transaction: invalid original_state"
        )
    if original_state.get("stage") != "cover_pending":
        raise ProjectStateError(
            "invalid cover selection transaction: invalid original stage"
        )
    if not isinstance(original_state.get("spec"), dict):
        raise ProjectStateError(
            "invalid cover selection transaction: invalid original spec"
        )
    if not isinstance(original_state.get("direct"), bool):
        raise ProjectStateError(
            "invalid cover selection transaction: invalid original direct flag"
        )
    if not isinstance(original_state.get("artifacts"), dict):
        raise ProjectStateError(
            "invalid cover selection transaction: invalid original artifacts"
        )


def _recover_cover_transaction(project, state, marker_path):
    transaction = _read_json(marker_path, "cover selection transaction")
    _validate_cover_transaction(transaction)
    target_cover = transaction["target_cover"]
    selected = project / "covers" / "selected.png"
    target = project / "covers" / target_cover
    backup = project / SELECTED_BACKUP_FILE
    committed = (
        state.get("stage") == "storyboard_pending"
        and state.get("selected_cover") == target_cover
    )
    if committed:
        try:
            _atomic_replace_file(target, selected)
        except ProjectStateError:
            return _restore_cover_transaction(project, transaction, marker_path)
        _cleanup_cover_transaction(marker_path, backup)
        return state
    return _restore_cover_transaction(project, transaction, marker_path)


def _require_stage(state, expected):
    actual = state.get("stage")
    if actual != expected:
        raise ProjectStateError(
            f"operation requires {expected}; current stage is {actual}"
        )


def _timestamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_spec(width, height, min_duration, max_duration):
    values = (width, height, min_duration, max_duration)
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        raise ProjectStateError("project spec values must be integers")
    if any(value <= 0 for value in values):
        raise ProjectStateError("project spec values must be positive")
    if min_duration > max_duration:
        raise ProjectStateError("project spec minimum duration exceeds maximum")


def _initial_artifact_status(direct):
    status = "pending_auto" if direct else "pending"
    return {name: status for name in ARTIFACT_NAMES}


def initialize_project(
    project,
    direct=False,
    width=1080,
    height=1920,
    min_duration=30,
    max_duration=60,
):
    project = Path(project)
    _validate_spec(width, height, min_duration, max_duration)
    if project.exists():
        raise ProjectStateError(f"project already exists: {project}")
    if not TEMPLATE_ROOT.is_dir():
        raise ProjectStateError(f"project template does not exist: {TEMPLATE_ROOT}")

    owns_project = False
    try:
        project.mkdir(parents=True, exist_ok=False)
        owns_project = True
        shutil.copytree(TEMPLATE_ROOT, project, dirs_exist_ok=True)
        state = {
            "stage": "production_ready" if direct else "title_pending",
            "spec": {
                "width": width,
                "height": height,
                "duration_min": min_duration,
                "duration_max": max_duration,
            },
            "direct": bool(direct),
            "artifacts": {
                "title": "title/candidates.md",
                "covers": "covers",
                "cover": "covers/selected.png",
                "script": "script/script.md",
                "storyboard": "script/storyboard.md",
            },
            "artifact_status": _initial_artifact_status(direct),
            "artifact_records": {},
            "confirmations": {"title": None, "cover": None, "storyboard": None},
            "outputs": {
                "video": "output/final-vertical.mp4",
                "cover": "output/cover.png",
                "subtitles": "output/subtitles.srt",
                "report": "output/production-report.md",
                "edit_dir": "edit",
            },
        }
        _write_state(project, state)
    except Exception:
        if owns_project and project.exists():
            shutil.rmtree(project)
        raise
    return state


def approve_title(project, title):
    title = title.strip()
    if not title:
        raise ProjectStateError("title must not be empty")
    state = _load_state(project)
    _require_stage(state, "title_pending")
    state["title"] = title
    state["stage"] = "cover_pending"
    state["artifact_status"]["title"] = "completed"
    state["confirmations"]["title"] = _timestamp()
    _write_state(project, state)
    return state


def select_cover(project, cover):
    state = _load_state(project)
    _require_stage(state, "cover_pending")
    cover_name = Path(cover).name
    if cover != cover_name or cover_name not in COVER_CANDIDATES:
        allowed = ", ".join(COVER_CANDIDATES)
        raise ProjectStateError(f"cover must be one of: {allowed}")

    covers_directory = Path(project) / "covers"
    missing = [
        name for name in COVER_CANDIDATES if not (covers_directory / name).is_file()
    ]
    if missing:
        raise ProjectStateError(
            "all cover candidates are required; missing: " + ", ".join(missing)
        )
    image_files = {
        path.name
        for path in covers_directory.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    }
    unexpected = sorted(image_files - set(COVER_CANDIDATES) - {"selected.png"})
    if unexpected:
        raise ProjectStateError(
            "unexpected cover image candidates: " + ", ".join(unexpected)
        )

    project = Path(project)
    selected = covers_directory / "selected.png"
    marker_path = project / TRANSACTION_FILE
    backup_path = project / SELECTED_BACKUP_FILE
    old_state = state
    new_state = dict(state)
    new_state["selected_cover"] = cover_name
    new_state["stage"] = "storyboard_pending"
    new_state["artifact_status"] = dict(state["artifact_status"])
    new_state["artifact_status"]["covers"] = "completed"
    new_state["artifact_status"]["cover"] = "completed"
    new_state["confirmations"] = dict(state["confirmations"])
    new_state["confirmations"]["cover"] = _timestamp()

    selected_existed = selected.is_file()
    if selected_existed:
        _atomic_replace_file(selected, backup_path)
    else:
        backup_path.unlink(missing_ok=True)
    transaction = {
        "original_state": old_state,
        "target_cover": cover_name,
        "selected_existed": selected_existed,
        "backup_path": SELECTED_BACKUP_FILE,
    }
    _atomic_write_json(marker_path, transaction, "cover selection transaction")

    try:
        _write_state(project, new_state)
    except Exception:
        _cleanup_cover_transaction(marker_path, backup_path)
        raise
    try:
        _atomic_replace_file(covers_directory / cover_name, selected)
    except ProjectStateError:
        try:
            _write_state(project, old_state)
        finally:
            _cleanup_cover_transaction(marker_path, backup_path)
        raise
    _cleanup_cover_transaction(marker_path, backup_path)
    return new_state


def approve_storyboard(project):
    state = _load_state(project)
    _require_stage(state, "storyboard_pending")
    state["stage"] = "production_ready"
    state["artifact_status"]["script"] = "completed"
    state["artifact_status"]["storyboard"] = "completed"
    state["confirmations"]["storyboard"] = _timestamp()
    _write_state(project, state)
    return state


def enable_direct(project):
    state = _load_state(project)
    if state.get("stage") not in {
        "title_pending",
        "cover_pending",
        "storyboard_pending",
        "production_ready",
    }:
        raise ProjectStateError(f"cannot enable direct from stage {state.get('stage')}")
    state["direct"] = True
    state["stage"] = "production_ready"
    statuses = state.setdefault("artifact_status", _initial_artifact_status(False))
    for name in ARTIFACT_NAMES:
        if statuses.get(name) != "completed":
            statuses[name] = "pending_auto"
    _write_state(project, state)
    return state


def _relative_artifact_path(project, path):
    project = Path(project).resolve()
    path = Path(path).resolve()
    try:
        relative = path.relative_to(project)
    except ValueError as error:
        raise ProjectStateError("artifact path must be inside project") from error
    if not path.exists():
        raise ProjectStateError(f"artifact path does not exist: {path}")
    return path, relative.as_posix()


def record_artifact(project, name, path, value=None):
    if name not in ARTIFACT_NAMES:
        raise ProjectStateError("artifact name must be title, covers, cover, script, or storyboard")
    state = _load_state(project)
    if not state.get("direct"):
        raise ProjectStateError("record-artifact is only allowed in direct mode")
    resolved, relative = _relative_artifact_path(project, path)
    canonical = (Path(project).resolve() / state["artifacts"][name]).resolve()
    if resolved != canonical:
        raise ProjectStateError(
            f"{name} artifact must use canonical path {state['artifacts'][name]}"
        )
    if name == "covers":
        if not resolved.is_dir():
            raise ProjectStateError("covers artifact path must be a directory")
        image_names = {
            item.name
            for item in resolved.iterdir()
            if item.is_file() and item.suffix.lower() in IMAGE_SUFFIXES
            and item.name != "selected.png"
        }
        if image_names != set(COVER_CANDIDATES):
            raise ProjectStateError("covers artifact requires exactly cover-a.png, cover-b.png, cover-c.png")
    elif name == "cover":
        if not resolved.is_file():
            raise ProjectStateError("cover artifact requires existing covers/selected.png")
        if value not in COVER_CANDIDATES:
            raise ProjectStateError(
                "cover artifact --value must be cover-a.png, cover-b.png, or cover-c.png"
            )
        candidate = resolved.parent / value
        if not candidate.is_file():
            raise ProjectStateError(f"cover candidate does not exist: {value}")
        if resolved.read_bytes() != candidate.read_bytes():
            raise ProjectStateError("selected cover bytes do not match chosen candidate")
    elif not resolved.is_file():
        raise ProjectStateError(f"{name} artifact path must be a file")

    if name == "title":
        if value is None or not value.strip():
            raise ProjectStateError("title artifact requires nonempty --value")
        value = value.strip()
    if name in {"script", "storyboard"}:
        if "<!-- LEO_VIDEO_CUT_TEMPLATE -->" in resolved.read_text(encoding="utf-8"):
            raise ProjectStateError(
                f"{name} artifact still contains the template marker"
            )

    record = {"path": relative, "recorded_at": _timestamp()}
    if value is not None:
        record["value"] = value
    state.setdefault("artifact_records", {})[name] = record
    state["artifact_status"][name] = "completed"
    if name == "title":
        state["title"] = value
    if name == "cover":
        state["selected_cover"] = value
    _write_state(project, state)
    return state


def show_project(project):
    return _load_state(project)


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("project", type=Path)
    init_parser.add_argument("--direct", action="store_true")
    init_parser.add_argument("--width", type=int, default=1080)
    init_parser.add_argument("--height", type=int, default=1920)
    init_parser.add_argument("--min-duration", type=int, default=30)
    init_parser.add_argument("--max-duration", type=int, default=60)

    title_parser = subparsers.add_parser("approve-title")
    title_parser.add_argument("project", type=Path)
    title_parser.add_argument("--title", required=True)

    cover_parser = subparsers.add_parser("select-cover")
    cover_parser.add_argument("project", type=Path)
    cover_parser.add_argument("--cover", required=True)

    storyboard_parser = subparsers.add_parser("approve-storyboard")
    storyboard_parser.add_argument("project", type=Path)

    direct_parser = subparsers.add_parser("direct")
    direct_parser.add_argument("project", type=Path)

    record_parser = subparsers.add_parser("record-artifact")
    record_parser.add_argument("project", type=Path)
    record_parser.add_argument("--name", required=True, choices=ARTIFACT_NAMES)
    record_parser.add_argument("--path", required=True, type=Path)
    record_parser.add_argument("--value")

    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("project", type=Path)
    return parser


def main(argv=None):
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "init":
            state = initialize_project(
                arguments.project,
                direct=arguments.direct,
                width=arguments.width,
                height=arguments.height,
                min_duration=arguments.min_duration,
                max_duration=arguments.max_duration,
            )
        elif arguments.command == "approve-title":
            state = approve_title(arguments.project, arguments.title)
        elif arguments.command == "select-cover":
            state = select_cover(arguments.project, arguments.cover)
        elif arguments.command == "approve-storyboard":
            state = approve_storyboard(arguments.project)
        elif arguments.command == "direct":
            state = enable_direct(arguments.project)
        elif arguments.command == "record-artifact":
            state = record_artifact(
                arguments.project,
                arguments.name,
                arguments.path,
                value=arguments.value,
            )
        else:
            state = show_project(arguments.project)
    except ProjectStateError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
