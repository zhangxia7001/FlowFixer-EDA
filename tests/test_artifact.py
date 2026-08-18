from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from flowfixer_eda.agent import FlowFixerAgent
from flowfixer_eda.cli import _materialize
from flowfixer_eda.dataset import load_tasks
from flowfixer_eda.demo import ContractVerifier, ReferencePatchBackend
from flowfixer_eda.metrics import summarize
from flowfixer_eda.models import Operation, Patch
from flowfixer_eda.parser import parse_log
from flowfixer_eda.tool_adapter import CommandSpec, CommandVerifier
from flowfixer_eda.validator import PatchRejected, apply_patch, validate_patch


ROOT = Path(__file__).resolve().parents[1]
PATCH_FIELDS = {
    "root_cause",
    "error_category",
    "failed_stage",
    "editable_files",
    "patches",
    "rerun_stage",
    "expected_effect",
    "risk_level",
}
OPERATION_FIELDS = {"file", "action", "target_match", "content", "justification"}
ALLOWED_ACTIONS = {"replace", "insert_before", "insert_after", "delete", "set_variable"}


class FlowFixerTests(unittest.TestCase):
    def setUp(self):
        self.tasks = load_tasks(ROOT / "dataset" / "tasks.json")

    def test_dataset_covers_eight_categories_and_schema(self):
        self.assertEqual(len(self.tasks), 8)
        self.assertEqual(len({task.error_category for task in self.tasks}), 8)
        for task in self.tasks:
            payload = task.reference_patch.to_dict()
            self.assertEqual(set(payload), PATCH_FIELDS)
            self.assertTrue(payload["patches"])
            self.assertTrue(all(set(operation) == OPERATION_FIELDS for operation in payload["patches"]))

    def test_json_schema_matches_supplementary_contract(self):
        schema = json.loads((ROOT / "schemas" / "patch.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["$schema"], "http://json-schema.org/draft-07/schema#")
        self.assertEqual(set(schema["required"]), PATCH_FIELDS)
        actions = set(schema["properties"]["patches"]["items"]["properties"]["action"]["enum"])
        self.assertEqual(actions, ALLOWED_ACTIONS)

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

    def test_all_five_operations_apply_deterministically(self):
        base = self.tasks[0]
        files = {
            "src/top.v": (
                "module top;\n"
                "wire a;\n"
                "MARK_BEFORE\n"
                "MARK_AFTER\n"
                "REMOVE_ME\n"
                "endmodule\n"
            ),
            "config.tcl": "set ::env(FP_CORE_UTIL) 98\n",
        }
        task = replace(
            base,
            error_category="config_error",
            failed_stage="floorplanning",
            editable_files=("src/top.v", "config.tcl"),
            files=files,
        )
        patch = Patch(
            root_cause="Five independent deterministic edits are required.",
            error_category="config_error",
            failed_stage="floorplanning",
            editable_files=("src/top.v", "config.tcl"),
            patches=(
                Operation("src/top.v", "replace", "wire a;", "wire b;", "Replace declaration."),
                Operation("src/top.v", "insert_before", "MARK_BEFORE", "// before\n", "Insert context."),
                Operation("src/top.v", "insert_after", "MARK_AFTER", "\n// after", "Insert context."),
                Operation("src/top.v", "delete", "REMOVE_ME", "", "Remove invalid marker."),
                Operation(
                    "config.tcl",
                    "set_variable",
                    "set ::env(FP_CORE_UTIL) 98",
                    "set ::env(FP_CORE_UTIL) 45",
                    "Restore verified project setting.",
                ),
            ),
            rerun_stage="floorplanning",
            expected_effect="Apply every permitted operation.",
            risk_level="medium",
        )
        with tempfile.TemporaryDirectory() as temp:
            workspace = _materialize(task, Path(temp))
            validate_patch(task, patch, workspace)
            apply_patch(patch, workspace)
            rtl = (workspace / "src/top.v").read_text(encoding="utf-8")
            config = (workspace / "config.tcl").read_text(encoding="utf-8")
        self.assertIn("wire b;", rtl)
        self.assertIn("// before\nMARK_BEFORE", rtl)
        self.assertIn("MARK_AFTER\n// after", rtl)
        self.assertNotIn("REMOVE_ME", rtl)
        self.assertEqual(config, "set ::env(FP_CORE_UTIL) 45\n")

    def test_duplicate_overlap_noop_and_constraint_weakening_are_rejected(self):
        task = self.tasks[0]
        operation = task.reference_patch.patches[0]
        noop = replace(
            task.reference_patch,
            patches=(replace(operation, content=operation.target_match),),
        )
        overlap = replace(
            task.reference_patch,
            patches=(
                operation,
                replace(operation, action="insert_after", content="// duplicate"),
            ),
        )
        sdc_task = self.tasks[2]
        unsafe = replace(
            sdc_task.reference_patch,
            patches=(
                Operation(
                    "constraints/top.sdc",
                    "replace",
                    "create_clock -period 10.0 [get_ports clk_misref]",
                    "create_clock -period 20.0 [get_ports clk_misref]",
                    "Unsafe relaxation.",
                ),
            ),
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rtl_workspace = _materialize(task, root)
            sdc_workspace = _materialize(sdc_task, root)
            for candidate in (noop, overlap):
                with self.assertRaises(PatchRejected):
                    validate_patch(task, candidate, rtl_workspace)
            with self.assertRaises(PatchRejected):
                validate_patch(sdc_task, unsafe, sdc_workspace)

    def test_repeated_rejected_patch_is_not_rerun(self):
        task = self.tasks[2]
        unsafe = replace(
            task.reference_patch,
            patches=(
                Operation(
                    "constraints/top.sdc",
                    "replace",
                    "create_clock -period 10.0 [get_ports clk_misref]",
                    "create_clock -period 20.0 [get_ports clk_misref]",
                    "Unsafe relaxation.",
                ),
            ),
        )

        class RepeatingBackend:
            def __init__(self):
                self.histories: list[list[str]] = []

            def propose(self, task, diagnostic, retrieved, feedback_history):
                self.histories.append(list(feedback_history))
                return unsafe

        backend = RepeatingBackend()
        agent = FlowFixerAgent(
            backend,
            ContractVerifier(),
            ROOT / "dataset" / "retrieval_corpus.json",
            max_attempts=2,
        )
        with tempfile.TemporaryDirectory() as temp:
            outcome = agent.repair(task, _materialize(task, Path(temp)))
        self.assertEqual(outcome.generated_patches, 2)
        self.assertEqual(outcome.valid_patches, 0)
        self.assertIn("rejected candidate", backend.histories[1][0])

    def test_trusted_tool_and_quality_commands(self):
        task = self.tasks[0]
        passing = CommandSpec("syntax", (sys.executable, "-c", "raise SystemExit(0)"), 10)
        quality = CommandSpec("timing", (sys.executable, "-c", "raise SystemExit(0)"), 10)
        verifier = CommandVerifier({"rtl_preparation": (passing,)}, (quality,))
        with tempfile.TemporaryDirectory() as temp:
            workspace = _materialize(task, Path(temp))
            result = verifier.verify(task, workspace, "rtl_preparation")
        self.assertTrue(result.flow_complete)
        self.assertTrue(result.quality_pass)
        self.assertEqual(result.gates, {"timing": True})


if __name__ == "__main__":
    unittest.main()
