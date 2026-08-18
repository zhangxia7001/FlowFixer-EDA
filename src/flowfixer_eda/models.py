from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class Operation:
    file: str
    action: str
    target_match: str
    content: str
    justification: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Operation":
        return cls(
            **{
                key: str(value[key])
                for key in ("file", "action", "target_match", "content", "justification")
            }
        )


@dataclass(frozen=True)
class Patch:
    root_cause: str
    error_category: str
    failed_stage: str
    editable_files: tuple[str, ...]
    patches: tuple[Operation, ...]
    rerun_stage: str
    expected_effect: str
    risk_level: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Patch":
        return cls(
            root_cause=str(value["root_cause"]),
            error_category=str(value["error_category"]),
            failed_stage=str(value["failed_stage"]),
            editable_files=tuple(str(item) for item in value["editable_files"]),
            patches=tuple(Operation.from_dict(item) for item in value["patches"]),
            rerun_stage=str(value["rerun_stage"]),
            expected_effect=str(value["expected_effect"]),
            risk_level=str(value["risk_level"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_cause": self.root_cause,
            "error_category": self.error_category,
            "failed_stage": self.failed_stage,
            "editable_files": list(self.editable_files),
            "patches": [operation.__dict__ for operation in self.patches],
            "rerun_stage": self.rerun_stage,
            "expected_effect": self.expected_effect,
            "risk_level": self.risk_level,
        }


@dataclass(frozen=True)
class Task:
    task_id: str
    design: str
    platform: str
    error_category: str
    failed_stage: str
    editable_files: tuple[str, ...]
    files: dict[str, str]
    log: str
    reference_patch: Patch
    expected_files: dict[str, str]
    quality_gates: dict[str, bool]


@dataclass(frozen=True)
class DiagnosticRecord:
    stage: str
    fatal_lines: tuple[str, ...]
    warning_lines: tuple[str, ...]
    referenced_files: tuple[str, ...]
    metrics: dict[str, float]


@dataclass(frozen=True)
class VerificationResult:
    flow_complete: bool
    quality_pass: bool
    feedback: str
    gates: dict[str, bool] = field(default_factory=dict)


class ProposalBackend(Protocol):
    def propose(
        self,
        task: Task,
        diagnostic: DiagnosticRecord,
        retrieved: list[str],
        feedback_history: list[str],
    ) -> Patch: ...


class Verifier(Protocol):
    def verify(self, task: Task, workspace: Path, rerun_stage: str) -> VerificationResult: ...
