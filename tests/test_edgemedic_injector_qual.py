import unittest

from edgemedic.gpu_pressure import injector_config, injector_hash, read_gpu_clock_mhz
from edgemedic.injector_qual import a3_blocked_reason, qualify_cycle, qualify_verdict


class InjectorQualTests(unittest.TestCase):
    def test_duty_cycle_changes_hash(self):
        left = injector_config(kind="gemm", load_ms=50, idle_ms=50)
        right = injector_config(kind="gemm", load_ms=80, idle_ms=20)
        self.assertNotEqual(injector_hash(left), injector_hash(right))
        self.assertNotEqual(injector_hash(left), injector_hash(injector_config(kind="bandwidth", load_ms=50, idle_ms=50)))

    def test_spike_is_not_sustained(self):
        gates = qualify_cycle(healthy_p95=180.0, fault_p95=202.0, hold_s=0.4, recovered_p95=181.0)
        self.assertFalse(gates["sustained"])
        self.assertFalse(gates["margin"])
        self.assertFalse(gates["pass"])

    def test_qualified_needs_five_consecutive_passes(self):
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

    def test_gpu_clock_is_null_off_jetson(self):
        clock = read_gpu_clock_mhz()
        self.assertTrue(clock is None or clock > 0)


if __name__ == "__main__":
    unittest.main()
