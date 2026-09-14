import unittest

from edgemedic.a3 import (
    downtime_s,
    first_mission_time,
    interleave_schedule,
    mission_loss,
    mission_ok,
    window_stats,
)
from edgemedic.gpu_pressure import INJECTOR_TYPE, injector_config, injector_hash
from edgemedic.inject import INJECTOR_FAULT_MODE
from edgemedic.provenance import FAULT_REAL_RESOURCE_PRESSURE, FAULT_SYNTHETIC_SNAPSHOT, collect_provenance


def _pt(t, utility=1.0, valid=True, v5=80.0, loc=20.0, profile="FULL", active=True):
    return (
        t,
        {
            "utility": utility,
            "output_valid": valid,
            "v5_latency_ms": v5,
            "locator_latency_ms": loc,
            "profile": profile,
            "inspection_active": active,
        },
    )


class A3MetricTests(unittest.TestCase):
    def test_interleave_is_balanced(self):
        alt = interleave_schedule(3, order="alternate")
        self.assertEqual(alt, ["restart_only", "sparse"] * 3)
        shuf = interleave_schedule(3, order="shuffle", seed=7)
        self.assertEqual(shuf.count("restart_only"), 3)
        self.assertEqual(shuf.count("sparse"), 3)

    def test_mission_loss_and_downtime(self):
        points = [
            _pt(0.0, 1.0, True),
            _pt(1.0, 0.0, False),
            _pt(2.0, 0.0, False),
            _pt(3.0, 0.95, True, profile="SPARSE"),
        ]
        self.assertEqual(mission_loss(points, 1.0, 4.0), 2.05)
        self.assertEqual(downtime_s(points, 1.0, 3.0), 2.0)

    def test_timeout_is_censored_not_a_number(self):
        points = [_pt(float(i), 0.0, False, v5=240.0) for i in range(0, 12)]
        self.assertIsNone(first_mission_time(points, 0.0, "FULL"))

    def test_sparse_window_uses_existing_v5_bar(self):
        points = [_pt(float(i) * 0.5, 0.95, True, v5=210.0, profile="SPARSE") for i in range(1, 30)]
        t_m = first_mission_time(points, 0.0, "SPARSE")
        self.assertIsNotNone(t_m)
        self.assertIsNone(first_mission_time(points, 0.0, "FULL"))

    def test_window_stats_need_cycles(self):
        points = [_pt(1.0)]
        ok, reason = mission_ok(window_stats(points, 1.0), "FULL")
        self.assertFalse(ok)
        self.assertEqual(reason, "cycles")


class InjectorContractTests(unittest.TestCase):
    def test_snapshot_inject_is_not_real_pressure(self):
        self.assertEqual(INJECTOR_FAULT_MODE, FAULT_SYNTHETIC_SNAPSHOT)
        self.assertNotEqual(INJECTOR_TYPE, "inject_v5_latency")

    def test_injector_hash_stable_for_same_config(self):
        cfg = injector_config(1024, 0)
        self.assertEqual(injector_hash(cfg), injector_hash(cfg))
        self.assertNotEqual(injector_hash(cfg), injector_hash(injector_config(2048, 0)))

    def test_provenance_lifts_injector_fields(self):
        payload = collect_provenance(
            reasoner="none",
            runtime_mode="dataset_replay",
            fault_mode=FAULT_REAL_RESOURCE_PRESSURE,
            experiment_config={
                "kind": "a3_restart_vs_sparse",
                "fault_injector_type": INJECTOR_TYPE,
                "fault_injector_hash": "abc",
                "recovery_strategy": "sparse",
            },
        )
        self.assertEqual(payload["fault_mode"], FAULT_REAL_RESOURCE_PRESSURE)
        self.assertEqual(payload["fault_injector_type"], INJECTOR_TYPE)
        self.assertEqual(payload["recovery_strategy"], "sparse")
        self.assertIn("experiment_config_hash", payload)


if __name__ == "__main__":
    unittest.main()
