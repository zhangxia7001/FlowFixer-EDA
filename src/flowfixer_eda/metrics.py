from __future__ import annotations

from .agent import RepairOutcome


def summarize(outcomes: list[RepairOutcome]) -> dict[str, float | int]:
    total = len(outcomes)
    if not total:
        return {"tasks": 0, "fc_rsr": 0.0, "sq_rsr": 0.0, "rca": 0.0, "pvr": 0.0, "ait": 0.0}
    completed = [item for item in outcomes if item.result.flow_complete]
    strict = [item for item in outcomes if item.result.flow_complete and item.result.quality_pass]
    generated = sum(item.generated_patches for item in outcomes)
    return {
        "tasks": total,
        "fc_rsr": len(completed) / total,
        "sq_rsr": len(strict) / total,
        "rca": sum(item.diagnosis_correct for item in outcomes) / total,
        "pvr": sum(item.valid_patches for item in outcomes) / generated if generated else 0.0,
        "ait": sum(item.attempts for item in completed) / len(completed) if completed else 0.0,
    }

