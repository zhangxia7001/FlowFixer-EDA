from __future__ import annotations

import json

from .models import DiagnosticRecord, Task


PATCH_CONTRACT = {
    "diagnosis": "concise root cause",
    "category": "one benchmark error category",
    "restart_stage": "earliest stage affected by the patch",
    "operations": [{"file": "relative editable path", "op": "replace", "old": "unique text", "new": "replacement"}],
}


def build_prompt(task: Task, record: DiagnosticRecord, retrieved: list[str], feedback: list[str]) -> str:
    return "\n".join(
        [
            "Diagnose the earliest initiating RTL-to-GDS fault and return JSON only.",
            f"Task: {task.task_id}; stage: {record.stage}; editable: {list(task.editable_files)}",
            "Fatal evidence:\n" + "\n".join(record.fatal_lines),
            "Retrieved guidance:\n" + "\n---\n".join(retrieved),
            "Previous feedback:\n" + "\n".join(feedback[-2:]),
            "Patch contract:\n" + json.dumps(PATCH_CONTRACT, indent=2),
            "Do not weaken reference constraints, bypass verification, or edit protected files.",
        ]
    )

