from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from .agent import FlowFixerAgent
from .dataset import load_tasks
from .demo import ContractVerifier, ReferencePatchBackend
from .metrics import summarize
from .parser import parse_log


def _materialize(task, root: Path) -> Path:
    workspace = root / task.task_id
    for name, content in task.files.items():
        target = workspace / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return workspace


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FlowFixer-EDA repair workflow")
    parser.add_argument("command", choices=("list", "inspect", "demo"))
    parser.add_argument("task_id", nargs="?")
    parser.add_argument("--dataset", default="dataset/tasks.json")
    parser.add_argument("--corpus", default="dataset/retrieval_corpus.json")
    parser.add_argument("--output", default="runs/demo")
    args = parser.parse_args(argv)
    tasks = load_tasks(args.dataset)
    if args.command == "list":
        for task in tasks:
            print(f"{task.task_id}\t{task.error_category}\t{task.failed_stage}\t{task.platform}")
        return 0
    if args.command == "inspect":
        task = next((item for item in tasks if item.task_id == args.task_id), None)
        if task is None:
            parser.error("inspect requires a valid task_id")
        print(json.dumps({**task.__dict__, "reference_patch": task.reference_patch.to_dict()}, indent=2, default=list))
        print(json.dumps(parse_log(task.log, task.failed_stage).__dict__, indent=2))
        return 0
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    outcomes = []
    agent = FlowFixerAgent(ReferencePatchBackend(), ContractVerifier(), args.corpus)
    with tempfile.TemporaryDirectory(prefix="flowfixer-dataset-") as temp:
        root = Path(temp)
        for task in tasks:
            outcomes.append(agent.repair(task, _materialize(task, root)))
    payload = {
        "summary": summarize(outcomes),
        "tasks": [
            {
                "task_id": item.task_id,
                "attempts": item.attempts,
                "diagnosis_correct": item.diagnosis_correct,
                "valid_patches": item.valid_patches,
                "generated_patches": item.generated_patches,
                "flow_complete": item.result.flow_complete,
                "quality_pass": item.result.quality_pass,
                "feedback": item.result.feedback,
                "gates": item.result.gates,
            }
            for item in outcomes
        ],
    }
    (output / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
