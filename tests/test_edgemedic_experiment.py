import tempfile
import unittest
from pathlib import Path

from edgemedic.candidate import generate_candidates
from edgemedic.experiment import run_software_inject, run_synthetic
from edgemedic.inject import patch_snapshot
from edgemedic.memory import MIN_REPEATED_SUCCESS, EpisodeStore
from edgemedic.metrics import classify_memory_proposal, trace_l2, unsafe_action_leakage
from edgemedic.bench import default_snapshot


class MetricsTests(unittest.TestCase):
    def test_blocked_wrong_memory_is_catch_not_harm(self):
        outcome = classify_memory_proposal(
            {"name": "set_inference_profile", "params": {"profile": "SPARSE"}},
            [{"tool": "set_locator_profile", "params": {"profile": "trt_fast"}}],
            abstain_allowed=False,
            blocked=True,
        )
        self.assertTrue(outcome["incorrect"])
        self.assertTrue(outcome["caught"])
        self.assertFalse(outcome["harm"])

    def test_ual_zero_when_unsafe_not_executed(self):
        self.assertEqual(unsafe_action_leakage(0, 3), 0.0)
        self.assertIsNone(unsafe_action_leakage(0, 0))
        table = trace_l2({"unsafe": True, "invalid": False, "action": None}, executed=False)
        self.assertEqual(table["guardian"]["blocked_count"], 1)
        self.assertEqual(table["executor"]["executed_count"], 0)


class InjectTests(unittest.TestCase):
    def test_locator_latency_patch_is_reversible(self):
        baseline = default_snapshot()
        injected = patch_snapshot(baseline, "inject_locator_latency")
        self.assertGreaterEqual(injected["locator"]["latency_ms"], 120)
        self.assertEqual(baseline["locator"]["latency_ms"], 18.0)


class ExperimentTests(unittest.TestCase):
    def test_synthetic_does_not_claim_nx(self):
        rows, summary = run_synthetic(runs=1)
        self.assertTrue(rows)
        self.assertFalse(summary["validated"])
        self.assertEqual(summary["nx_workload"], "not-run")
        self.assertIsNone(rows[0]["mttr_ms"])

    def test_software_inject_resets(self):
        rows = run_software_inject()
        self.assertGreaterEqual(len(rows), 6)
        self.assertTrue(all(item["reset"] == "ok" for item in rows))
        self.assertTrue(all(item["fault_mode"] == "synthetic_snapshot" for item in rows))

    def test_policy_candidate_is_not_deployed(self):
        store = EpisodeStore(Path(tempfile.mkdtemp()) / "episodes.json")
        for _ in range(MIN_REPEATED_SUCCESS):
            store.record("V5_OVERLOAD", "set_inference_profile", {"profile": "SPARSE"}, verify_level="function")
        items = generate_candidates(store)
        self.assertEqual(items[0]["status"], "candidate")
        self.assertEqual(items[0]["action"]["params"]["profile"], "SPARSE")
