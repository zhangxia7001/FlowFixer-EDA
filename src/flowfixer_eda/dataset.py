from __future__ import annotations

import json
from pathlib import Path

from .models import Patch, Task


def load_tasks(path: str | Path) -> list[Task]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    tasks: list[Task] = []
    seen: set[str] = set()
    for raw in payload["tasks"]:
        task_id = str(raw["task_id"])
        if task_id in seen:
            raise ValueError(f"duplicate task_id: {task_id}")
        seen.add(task_id)
        tasks.append(
            Task(
                task_id=task_id,
                design=str(raw["design"]),
                platform=str(raw["platform"]),
                category=str(raw["category"]),
                failed_stage=str(raw["failed_stage"]),
                editable_files=tuple(raw["editable_files"]),
                files={str(k): str(v) for k, v in raw["files"].items()},
                log=str(raw["log"]),
                reference_patch=Patch.from_dict(raw["reference_patch"]),
                expected_files={str(k): str(v) for k, v in raw["expected_files"].items()},
                quality_gates={str(k): bool(v) for k, v in raw["quality_gates"].items()},
            )
        )
    return tasks

