from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path, PurePosixPath

from .models import Operation, Patch, Task


ALLOWED_ACTIONS = {"replace", "insert_before", "insert_after", "delete", "set_variable"}
ALLOWED_CATEGORIES = {
    "rtl_error",
    "port_mismatch",
    "sdc_error",
    "config_error",
    "floorplan_error",
    "placement_error",
    "routing_error",
    "timing_error",
}
ALLOWED_RISK_LEVELS = {"low", "medium", "high"}
_PROTECTED_SUFFIXES = {".lef", ".lib", ".gds", ".oas"}
_DISABLE_KEYS = (
    "RUN_DRC",
    "RUN_ROUTING",
    "RUN_MAGIC",
    "RUN_KLAYOUT",
    "QUIT_ON_TIMING_VIOLATIONS",
    "QUIT_ON_DRC_ERRORS",
    "QUIT_ON_LVS_ERROR",
)


class PatchRejected(ValueError):
    pass


def patch_fingerprint(patch: Patch) -> str:
    encoded = json.dumps(patch.to_dict(), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _safe_relative(path: str) -> bool:
    normalized = path.replace("\\", "/")
    candidate = PurePosixPath(normalized)
    return not candidate.is_absolute() and ".." not in candidate.parts


def _reject_unsafe(operation: Operation) -> None:
    old = operation.target_match.lower()
    new = operation.content.lower()
    if "set_false_path" in new and "set_false_path" not in old:
        raise PatchRejected("new broad false-path constraints are not allowed")

    old_period = re.search(r"create_clock\s+-period\s+(\d+(?:\.\d+)?)", old)
    new_period = re.search(r"create_clock\s+-period\s+(\d+(?:\.\d+)?)", new)
    if old_period and new_period and float(new_period.group(1)) > float(old_period.group(1)):
        raise PatchRejected("clock-period relaxation is not allowed")

    if operation.action == "delete" and any(
        marker in old for marker in ("create_clock", "set_input_delay", "set_output_delay")
    ):
        raise PatchRejected("reference timing constraints cannot be deleted")

    for key in _DISABLE_KEYS:
        if key.lower() in new and re.search(r"(?:\s|[=:])(?:0|false|no)(?:\s|$)", new):
            raise PatchRejected(f"verification bypass is not allowed: {key}")

    bypass_markers = ("bypass_drc", "disable_drc", "skip_routing", "skip_timing")
    if any(marker in new for marker in bypass_markers):
        raise PatchRejected("timing, DRC, or routing verification cannot be bypassed")


def _validate_operation(task: Task, patch: Patch, operation: Operation, workspace: Path) -> tuple[int, int]:
    if operation.action not in ALLOWED_ACTIONS:
        raise PatchRejected(f"unsupported operation: {operation.action}")
    if not operation.justification.strip():
        raise PatchRejected("operation justification must not be empty")
    if not operation.target_match:
        raise PatchRejected("target_match must not be empty")
    if not _safe_relative(operation.file):
        raise PatchRejected(f"unsafe relative path: {operation.file}")
    if operation.file not in task.editable_files or operation.file not in patch.editable_files:
        raise PatchRejected(f"file is outside editable allowlist: {operation.file}")
    if Path(operation.file).suffix.lower() in _PROTECTED_SUFFIXES:
        raise PatchRejected(f"protected generated or library file: {operation.file}")

    target = workspace / Path(operation.file)
    if not target.is_file():
        raise PatchRejected(f"target does not exist: {operation.file}")
    current = target.read_text(encoding="utf-8")
    if current.count(operation.target_match) != 1:
        raise PatchRejected(f"target_match must occur exactly once: {operation.file}")

    if operation.action in {"replace", "set_variable"} and operation.content == operation.target_match:
        raise PatchRejected("no-op replacement is not allowed")
    if operation.action in {"insert_before", "insert_after"} and not operation.content:
        raise PatchRejected("insert operations require non-empty content")
    if operation.action == "delete" and operation.content:
        raise PatchRejected("delete operations require empty content")
    if operation.action == "set_variable":
        if target.suffix.lower() not in {".tcl", ".json"}:
            raise PatchRejected("set_variable is restricted to project configuration files")
        assignment = operation.target_match.lstrip()
        if not (assignment.startswith("set ") or assignment.startswith('"')):
            raise PatchRejected("set_variable target must be an existing configuration assignment")

    _reject_unsafe(operation)
    start = current.index(operation.target_match)
    return start, start + len(operation.target_match)


def validate_patch(
    task: Task,
    patch: Patch,
    workspace: Path,
    seen: set[str] | dict[str, str] | None = None,
) -> str:
    fingerprint = patch_fingerprint(patch)
    if seen is not None and fingerprint in seen:
        raise PatchRejected("repeated patch candidate")
    if not patch.root_cause.strip() or not patch.expected_effect.strip():
        raise PatchRejected("root_cause and expected_effect must not be empty")
    if patch.error_category not in ALLOWED_CATEGORIES:
        raise PatchRejected(f"unsupported error category: {patch.error_category}")
    if patch.error_category != task.error_category:
        raise PatchRejected("predicted error category does not match the task contract")
    if patch.failed_stage != task.failed_stage:
        raise PatchRejected("failed_stage does not match the diagnostic task")
    if patch.risk_level not in ALLOWED_RISK_LEVELS:
        raise PatchRejected(f"unsupported risk level: {patch.risk_level}")
    if not patch.rerun_stage.strip():
        raise PatchRejected("rerun_stage must not be empty")
    if len(patch.editable_files) != len(set(patch.editable_files)):
        raise PatchRejected("editable_files must be unique")
    if set(patch.editable_files) != set(task.editable_files):
        raise PatchRejected("editable_files must match the task-authorized allowlist")
    if not patch.patches:
        raise PatchRejected("patch contains no operations")

    operation_keys: set[tuple[str, str, str, str]] = set()
    spans: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for operation in patch.patches:
        key = (operation.file, operation.action, operation.target_match, operation.content)
        if key in operation_keys:
            raise PatchRejected("duplicate operation is not allowed")
        operation_keys.add(key)
        start, end = _validate_operation(task, patch, operation, workspace)
        for previous_start, previous_end in spans[operation.file]:
            if max(start, previous_start) < min(end, previous_end):
                raise PatchRejected(f"overlapping operations are not allowed: {operation.file}")
        spans[operation.file].append((start, end))
    return fingerprint


def apply_patch(patch: Patch, workspace: Path) -> None:
    by_file: dict[str, list[Operation]] = defaultdict(list)
    for operation in patch.patches:
        by_file[operation.file].append(operation)

    for filename, operations in by_file.items():
        target = workspace / Path(filename)
        current = target.read_text(encoding="utf-8")
        positioned = [
            (current.index(operation.target_match), operation)
            for operation in operations
        ]
        for start, operation in sorted(positioned, key=lambda item: item[0], reverse=True):
            end = start + len(operation.target_match)
            if operation.action in {"replace", "set_variable"}:
                replacement = operation.content
            elif operation.action == "insert_before":
                replacement = operation.content + operation.target_match
            elif operation.action == "insert_after":
                replacement = operation.target_match + operation.content
            elif operation.action == "delete":
                replacement = ""
            else:  # guarded by validate_patch
                raise PatchRejected(f"unsupported operation: {operation.action}")
            current = current[:start] + replacement + current[end:]
        target.write_text(current, encoding="utf-8")
