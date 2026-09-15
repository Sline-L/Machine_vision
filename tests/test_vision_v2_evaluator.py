import unittest
from pathlib import Path

from edgemedic.vision_v2_evaluator import (
    choose_threshold,
    load_merged_val,
    pareto_class,
    q_d_u,
    refuse_locked,
    run_evaluation,
)


class VisionV2EvaluatorTests(unittest.TestCase):
    def test_refuse_test_scratch(self):
        with self.assertRaises(ValueError):
            refuse_locked(Path("dataset_defects/images/test_scratch/x.jpg"))

    def test_choose_threshold_ordering(self):
        labels = [0, 0, 1, 1]
        probs = [0.05, 0.15, 0.85, 0.95]
        row, key = choose_threshold(labels, probs, 0.20)
        self.assertTrue(key[0])
        self.assertGreaterEqual(row["recall"], 0.5)

    def test_q_d_u(self):
        qd, u = q_d_u(0.9, 0.1)
        self.assertAlmostEqual(qd, 0.9)
        self.assertAlmostEqual(u, 0.95)

    def test_run_pareto_on_committed_val_csvs(self):
        root = Path(__file__).resolve().parents[1]
        full_csv = root / "final" / "val_predictions.csv"
        cls_csv = root / "docs" / "capability-extraction" / "configs" / "classifier_only_mean.val_predictions.csv"
        if not full_csv.is_file() or not cls_csv.is_file():
            self.skipTest("val CSV artifacts missing")
        payload = run_evaluation(full_csv, cls_csv, root / "var" / "test_vision_v2_pareto")
        self.assertEqual(payload["n_val"], 150)
        full = next(c for c in payload["candidates"] if c["candidate_id"] == "FULL_a0.25_mean")
        self.assertTrue(full["target_met"])
        self.assertGreater(full["Q_D_val"], 0.9)
        cls = next(c for c in payload["candidates"] if c["candidate_id"] == "classifier_mean")
        self.assertTrue(cls["target_met"])


if __name__ == "__main__":
    unittest.main()
