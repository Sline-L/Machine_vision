import unittest

from edgemedic.bench import family_table, run_suite
from edgemedic.experiment import run_synthetic
from edgemedic.provenance import collect_provenance, summarize_samples


class ProvenanceTests(unittest.TestCase):
    def test_local_bundle_id_is_recorded(self):
        payload = collect_provenance(reasoner="qwen", runtime_mode="synthetic")
        self.assertEqual(payload["reasoner"], "qwen3-4b")
        self.assertEqual(payload["bundle_id"], "scratch-v5-2026-09-14")
        self.assertEqual(payload["locator_engine_sha256"], "aec2d9b56a522683b109428fdd8f95cc7600b617d18787f6c4a6838b58a5d892")
        self.assertEqual(payload["runtime_commit"], payload["agent_commit"])
        self.assertEqual(payload["fault_mode"], "none")
        self.assertIn("experiment_config_hash", payload)
        self.assertEqual(len(payload["experiment_config_hash"]), 64)

    def test_fault_modes_are_not_mixed_by_hash(self):
        from edgemedic.provenance import FAULT_REAL_RESOURCE_PRESSURE, FAULT_SYNTHETIC_SNAPSHOT, experiment_config_hash

        left = experiment_config_hash({"fault_mode": FAULT_SYNTHETIC_SNAPSHOT})
        right = experiment_config_hash({"fault_mode": FAULT_REAL_RESOURCE_PRESSURE})
        self.assertNotEqual(left, right)

    def test_replay_device_sets_runtime_mode(self):
        payload = collect_provenance(snapshot={"camera": {"device": "replay:/tmp/frames"}})
        self.assertEqual(payload["runtime_mode"], "dataset_replay")

    def test_sample_summary_is_not_claimed_validated(self):
        summary = summarize_samples(
            [
                {"output_valid": True, "locator_latency_ms": 40, "v5_latency_ms": 80, "gpu_util": 30},
                {"output_valid": True, "locator_latency_ms": 50, "v5_latency_ms": 90, "gpu_util": 40},
                {"output_valid": False, "locator_latency_ms": 400, "v5_latency_ms": 400},
            ]
        )
        self.assertEqual(summary["cycle_count"], 3)
        self.assertAlmostEqual(summary["valid_ratio"], 2 / 3, places=4)
        self.assertFalse(summary["experimentally_validated"])
        self.assertIsNotNone(summary["locator"]["p95"])


class FamilyTableTests(unittest.TestCase):
    def test_mock_suite_exposes_family_table_and_provenance(self):
        summary = run_suite(reasoner="mock")
        self.assertIn("family_table", summary)
        self.assertFalse(summary["experimentally_validated"])
        self.assertEqual(summary["provenance"]["bundle_id"], "scratch-v5-2026-09-14")
        self.assertTrue(summary["family_table"])

    def test_family_table_counts_l2_rows_only(self):
        table = family_table(
            [
                {"family": "known-simple", "l2_metrics": None},
                {
                    "family": "unsafe-request",
                    "l2": {"abstain": False, "unsafe": True, "invalid": False, "action": None},
                    "l2_metrics": {"unsafe": True, "invalid": False, "tool_ok": None},
                },
                {
                    "family": "known-composite",
                    "l2": {"abstain": False, "unsafe": False, "invalid": False, "action": {"name": "set_inference_profile"}},
                    "l2_metrics": {"unsafe": False, "invalid": False, "tool_ok": True},
                },
            ]
        )
        self.assertEqual(table["unsafe-request"]["unsafe"], 1)
        self.assertEqual(table["known-composite"]["correct_action"], 1)
        self.assertNotIn("known-simple", table)


class SyntheticProvenanceTests(unittest.TestCase):
    def test_synthetic_summary_carries_provenance(self):
        _rows, summary = run_synthetic(runs=1)
        self.assertIn("provenance", summary)
        self.assertEqual(summary["provenance"]["fault_mode"], "synthetic_snapshot")


if __name__ == "__main__":
    unittest.main()
