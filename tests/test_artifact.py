from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from flowfixer_eda.agent import FlowFixerAgent
from flowfixer_eda.cli import _materialize
from flowfixer_eda.dataset import load_tasks
from flowfixer_eda.demo import ContractVerifier, ReferencePatchBackend
from flowfixer_eda.metrics import summarize
from flowfixer_eda.parser import parse_log
from flowfixer_eda.validator import PatchRejected, validate_patch


ROOT = Path(__file__).resolve().parents[1]


class FlowFixerTests(unittest.TestCase):
    def setUp(self):
        self.tasks = load_tasks(ROOT / "dataset" / "tasks.json")

    def test_dataset_covers_eight_categories(self):
        self.assertEqual(len(self.tasks), 8)
        self.assertEqual(len({task.category for task in self.tasks}), 8)

    def test_parser_extracts_evidence(self):
        record = parse_log(self.tasks[0].log, self.tasks[0].failed_stage)
        self.assertTrue(record.fatal_lines)
        self.assertIn("src/top.v", record.referenced_files)

    def test_demo_repairs_every_task(self):
        agent = FlowFixerAgent(
            ReferencePatchBackend(), ContractVerifier(), ROOT / "dataset" / "retrieval_corpus.json"
        )
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            outcomes = [agent.repair(task, _materialize(task, work)) for task in self.tasks]
        summary = summarize(outcomes)
        self.assertEqual(summary["fc_rsr"], 1.0)
        self.assertEqual(summary["sq_rsr"], 1.0)
        self.assertEqual(summary["pvr"], 1.0)

    def test_repeated_patch_is_rejected(self):
        task = self.tasks[0]
        with tempfile.TemporaryDirectory() as temp:
            workspace = _materialize(task, Path(temp))
            fingerprint = validate_patch(task, task.reference_patch, workspace, set())
            with self.assertRaises(PatchRejected):
                validate_patch(task, task.reference_patch, workspace, {fingerprint})


if __name__ == "__main__":
    unittest.main()
