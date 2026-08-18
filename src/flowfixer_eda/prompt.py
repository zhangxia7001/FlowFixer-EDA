from __future__ import annotations

import json

from .models import DiagnosticRecord, Task


PATCH_CONTRACT = {
    "root_cause": "concise initiating cause",
    "error_category": "one of the eight snake_case error categories",
    "failed_stage": "earliest fatal flow stage",
    "editable_files": ["task-authorized relative path"],
    "patches": [
        {
            "file": "relative editable path",
            "action": "replace|insert_before|insert_after|delete|set_variable",
            "target_match": "text that occurs exactly once",
            "content": "replacement or inserted content",
            "justification": "why the operation repairs the root cause",
        }
    ],
    "rerun_stage": "earliest stage affected by the patch",
    "expected_effect": "expected executable outcome",
    "risk_level": "low|medium|high",
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
