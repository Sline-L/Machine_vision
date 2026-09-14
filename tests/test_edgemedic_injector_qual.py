import unittest

from edgemedic.gpu_pressure import injector_config, injector_hash, read_emc_mhz, read_gpu_clock_mhz
from edgemedic.injector_qual import a3_blocked_reason, qualify_cycle, qualify_verdict, selectivity_report, time_windows


class InjectorQualTests(unittest.TestCase):
    def test_duty_cycle_changes_hash(self):
        left = injector_config(kind="bandwidth", load_ms=50, idle_ms=50)
        right = injector_config(kind="bandwidth", load_ms=80, idle_ms=20)
        self.assertNotEqual(injector_hash(left), injector_hash(right))
        self.assertNotEqual(injector_hash(left), injector_hash(injector_config(kind="sm", load_ms=50, idle_ms=50)))

    def test_spike_is_not_sustained(self):
        gates = qualify_cycle(healthy_p95=180.0, fault_p95=202.0, hold_s=0.4, recovered_p95=181.0)
        self.assertFalse(gates["sustained"])
        self.assertFalse(gates["margin"])
        self.assertFalse(gates["pass"])

    def test_admission_gate_is_190_not_envelope(self):
        jitter = qualify_cycle(181.0, 240.0, 5.0, 188.0)
        self.assertTrue(jitter["reversible"])
        self.assertFalse(jitter["in_expected_envelope"])
        self.assertTrue(jitter["pass"])
        leftover = qualify_cycle(181.0, 240.0, 5.0, 194.0)
        self.assertFalse(leftover["reversible"])
        self.assertFalse(leftover["pass"])
        one = qualify_cycle(181.0, 240.0, 3.0, 183.0)
        self.assertTrue(one["pass"])
        self.assertFalse(qualify_verdict([one] * 4)["fault_injector_qualified"])
        self.assertTrue(qualify_verdict([one] * 5)["fault_injector_qualified"])
        failed = qualify_cycle(181.0, 202.0, 0.4, 181.0)
        self.assertFalse(qualify_verdict([one] * 4 + [failed])["fault_injector_qualified"])

    def test_a3_blocked_without_qualification(self):
        self.assertIsNotNone(a3_blocked_reason(None))
        self.assertIsNotNone(a3_blocked_reason({"fault_injector_qualified": False}))
        self.assertIsNone(a3_blocked_reason({"fault_injector_qualified": True}))

    def test_time_windows_are_non_overlapping(self):
        rows = [{"t": float(i), "v5_latency_ms": 160 + i, "output_valid": True, "locator_latency_ms": 50, "overload": False} for i in range(0, 45)]
        windows = time_windows(rows, 15.0)
        self.assertEqual(len(windows), 3)
        self.assertEqual(windows[0]["t0_s"], 0.0)
        self.assertEqual(windows[2]["t0_s"], 30.0)
        clock = read_gpu_clock_mhz()
        self.assertTrue(clock is None or clock > 0)
        emc = read_emc_mhz()
        self.assertTrue(emc is None or emc > 0)

    def test_selectivity_is_report_only(self):
        report = selectivity_report(
            {"v5_p95": 180.0, "locator": {"p95": 52.0}, "valid_ratio": 0.99},
            {"v5_p95": 240.0, "locator": {"p95": 55.0}, "valid_ratio": 0.98},
        )
        self.assertFalse(report["hard_gated"])
        self.assertEqual(report["v5_delta_ms"], 60.0)
        self.assertEqual(report["locator_delta_ms"], 3.0)


if __name__ == "__main__":
    unittest.main()
