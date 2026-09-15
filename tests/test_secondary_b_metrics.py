"""Unit tests for Secondary B continuity accounting."""

import unittest

from edgemedic.secondary_b_metrics import account_demand_opportunities, percentile
from gp.types import InspectionResult


class SecondaryBMetricsTests(unittest.TestCase):
    def test_percentile(self):
        self.assertEqual(percentile([1, 2, 3, 4], 50), 2.5)

    def test_inspection_age_and_lag(self):
        result = InspectionResult(
            annotated_frame=None,
            source_frame_seq=10,
            source_capture_ts=100.0,
            inspection_start_ts=100.05,
            inspection_end_ts=100.25,
            latest_frame_seq_at_completion=14,
        )
        self.assertAlmostEqual(result.inspection_age_ms, 250.0)
        self.assertEqual(result.frame_lag, 4)

    def test_intentional_vs_pressure(self):
        # One inspect [0.0, 0.15], interval 0.20 → gated until 0.35
        inspects = [{"start": 0.0, "end": 0.15, "valid": True}]
        demands = [0.05, 0.20, 0.40]
        # 0.05 in-flight → intentional
        # 0.20 gated → intentional
        # 0.40 eligible, no following inspect → pressure_miss
        out = account_demand_opportunities(demands, inspects, 0.20)
        self.assertEqual(out["intentional_skip"], 2)
        self.assertEqual(out["eligible_opportunity_count"], 1)
        self.assertEqual(out["pressure_miss"], 1)


if __name__ == "__main__":
    unittest.main()
