"""P0 4B Agent unit tests — observe-only by default; no live Control required."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from edgemedic.adapter import adapt_snapshot, specialist_view
from edgemedic.authority import decide_execution
from edgemedic.observe import load_json
from edgemedic.policy import Memory, classify_fault, decide
from edgemedic.readonly_client import ObserveOnlyViolation, ReadOnlyControlClient
from edgemedic.runtime import EXECUTE_OBSERVE, LoopState, run_once

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "docs" / "midterm" / "scenarios"


class AdapterTests(unittest.TestCase):
    def test_v2_specialists_hoisted(self):
        snap = load_json(SCENARIO / "A_healthy.json")
        adapted = adapt_snapshot(snap)
        self.assertIn("scratch_v5", adapted)
        view = specialist_view(adapted)
        self.assertIn("scratch_v5", view)
        self.assertIn("missing_hole_v1", view)

    def test_missing_fields_marked(self):
        adapted = adapt_snapshot({"camera": {"opened": True}})
        self.assertEqual(adapted["scratch_v5"], {})
        self.assertTrue(adapted["inference"].get("unavailable"))


class L2RouteTests(unittest.TestCase):
    def test_unknown_scratch_has_no_l1(self):
        snap = adapt_snapshot(load_json(SCENARIO / "L2_unknown_scratch.json"))
        fault = classify_fault(snap, Memory())
        self.assertEqual(fault, "UNKNOWN_SCRATCH_V5")
        self.assertIsNone(decide(snap, Memory()))

    def test_run_once_observe_invokes_l2_mock(self):
        snap = load_json(SCENARIO / "L2_unknown_scratch.json")
        client = ReadOnlyControlClient(snapshot=snap)
        fake = {
            "action": {"name": "restart_worker", "params": {}},
            "latency_s": 1.5,
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "tokens": 120,
            "decode": "grammar",
            "protocol_status": "valid_structured",
            "raw": '{"tool":"restart_worker","params":{}}',
        }
        with mock.patch("edgemedic.runtime.complete_report", return_value=fake):
            cycle = run_once(
                client,
                LoopState(),
                llm_url="http://127.0.0.1:8080",
                execution_mode=EXECUTE_OBSERVE,
                disable_memory=True,
                snapshot_overlay=snap,
            )
        self.assertEqual(cycle["route"]["selected"], "L2")
        self.assertTrue(cycle["l2"]["invoked"])
        self.assertFalse(cycle["actually_executed"])
        self.assertTrue(cycle["ACTUAL_EXECUTION_DISABLED"])
        self.assertEqual(cycle["proposed_action"]["name"], "restart_worker")

    def test_authority_blocks_high_risk_l2(self):
        gate = decide_execution(
            {"name": "set_locator_profile", "params": {"profile": "trt_fast"}},
            source="reasoner",
            live_research=True,
        )
        self.assertFalse(gate["would_execute"])
        self.assertEqual(gate["execution_authority"], "DRY_RUN")

    def test_authority_allows_low_risk(self):
        gate = decide_execution({"name": "resume_inspection", "params": {}}, source="reasoner")
        self.assertTrue(gate["would_execute"])

    def test_readonly_never_posts(self):
        client = ReadOnlyControlClient(snapshot={})
        with self.assertRaises(ObserveOnlyViolation):
            client.post_action("resume_inspection", {})


class ObserveL1Tests(unittest.TestCase):
    def test_paused_proposes_but_does_not_execute(self):
        snap = load_json(SCENARIO / "B_inspection_paused.json")
        client = ReadOnlyControlClient(snapshot=snap)
        cycle = run_once(client, LoopState(), llm_url=None, execution_mode=EXECUTE_OBSERVE, snapshot_overlay=snap)
        self.assertEqual(cycle["fault"], "INSPECTION_PAUSED")
        self.assertEqual(cycle["proposed_action"]["name"], "resume_inspection")
        self.assertFalse(cycle["actually_executed"])


if __name__ == "__main__":
    unittest.main()
