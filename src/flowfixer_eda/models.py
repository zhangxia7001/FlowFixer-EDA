from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class Operation:
    file: str
    op: str
    old: str
    new: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Operation":
        return cls(**{key: value[key] for key in ("file", "op", "old", "new")})


@dataclass(frozen=True)
class Patch:
    diagnosis: str
    category: str
    restart_stage: str
    operations: tuple[Operation, ...]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Patch":
        return cls(
            diagnosis=str(value["diagnosis"]),
            category=str(value["category"]),
            restart_stage=str(value["restart_stage"]),
            operations=tuple(Operation.from_dict(item) for item in value["operations"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "diagnosis": self.diagnosis,
            "category": self.category,
            "restart_stage": self.restart_stage,
            "operations": [operation.__dict__ for operation in self.operations],
        }


@dataclass(frozen=True)
class Task:
    task_id: str
    design: str
    platform: str
    category: str
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
    def verify(self, task: Task, workspace: Path, restart_stage: str) -> VerificationResult: ...

