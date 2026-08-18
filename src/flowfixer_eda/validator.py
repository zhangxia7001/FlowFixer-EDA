from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath

from .models import Patch, Task


class PatchRejected(ValueError):
    pass


def patch_fingerprint(patch: Patch) -> str:
    encoded = json.dumps(patch.to_dict(), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _safe_relative(path: str) -> bool:
    normalized = path.replace("\\", "/")
    candidate = PurePosixPath(normalized)
    return not candidate.is_absolute() and ".." not in candidate.parts


def validate_patch(task: Task, patch: Patch, workspace: Path, seen: set[str]) -> str:
    fingerprint = patch_fingerprint(patch)
    if fingerprint in seen:
        raise PatchRejected("repeated patch candidate")
    if patch.category != task.category:
        raise PatchRejected("diagnosed category does not match the task contract")
    if not patch.operations:
        raise PatchRejected("patch contains no operations")
    for operation in patch.operations:
        if operation.op != "replace":
            raise PatchRejected(f"unsupported operation: {operation.op}")
        if not _safe_relative(operation.file) or operation.file not in task.editable_files:
            raise PatchRejected(f"file is outside editable allowlist: {operation.file}")
        target = workspace / Path(operation.file)
        if not target.is_file():
            raise PatchRejected(f"target does not exist: {operation.file}")
        current = target.read_text(encoding="utf-8")
        if current.count(operation.old) != 1:
            raise PatchRejected(f"replacement anchor must occur exactly once: {operation.file}")
        lowered = operation.new.lower()
        if "set_false_path" in lowered and "set_false_path" not in operation.old.lower():
            raise PatchRejected("new broad false-path constraints are not allowed")
        old_period = re.search(r"create_clock\s+-period\s+(\d+(?:\.\d+)?)", operation.old)
        new_period = re.search(r"create_clock\s+-period\s+(\d+(?:\.\d+)?)", operation.new)
        if old_period and new_period and float(new_period.group(1)) > float(old_period.group(1)):
            raise PatchRejected("clock-period relaxation is not allowed")
    return fingerprint


def apply_patch(patch: Patch, workspace: Path) -> None:
    for operation in patch.operations:
        target = workspace / Path(operation.file)
        current = target.read_text(encoding="utf-8")
        target.write_text(current.replace(operation.old, operation.new, 1), encoding="utf-8")

