"""Observe-only midterm Agent demo tests — post_action must hard-fail."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from edgemedic.memory import EpisodeStore
from edgemedic.observe import diagnose, load_json, normalize_snapshot
from edgemedic.policy import Memory, classify_fault, decide
from edgemedic.readonly_client import ObserveOnlyViolation, ReadOnlyControlClient

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "docs" / "midterm" / "scenarios"
FROZEN = ROOT / "docs" / "midterm" / "frozen"


class ReadOnlyClientTests(unittest.TestCase):
    def test_post_action_raises(self):
        client = ReadOnlyControlClient(snapshot={"ok": True})
        self.assertEqual(client.get_state()["ok"], True)
        with self.assertRaises(ObserveOnlyViolation):
            client.post_action("restart_camera", {})
        with self.assertRaises(ObserveOnlyViolation):
            client.preview_action("restart_camera", {})


class ScenarioDiagnosisTests(unittest.TestCase):
    def test_healthy_proposes_nothing(self):
        snap = load_json(SCENARIO / "A_healthy.json")
        report = diagnose(snap, scenario="A_healthy", input_source="SYNTHETIC")
        self.assertIsNone(report["fault"])
        self.assertIsNone(report["proposed_action"])
        self.assertFalse(report["actually_executed"])
        self.assertFalse(report["recovery_claimed"])

    def test_inspection_paused_proposes_resume(self):
        snap = load_json(SCENARIO / "B_inspection_paused.json")
        report = diagnose(snap, scenario="B_inspection_paused")
        self.assertEqual(report["fault"], "INSPECTION_PAUSED")
        self.assertEqual(report["proposed_action"]["name"], "resume_inspection")
        self.assertEqual(report["proposed_action"]["layer"], "L1")
        self.assertFalse(report["actually_executed"])

    def test_camera_stale_proposes_restart(self):
        snap = load_json(SCENARIO / "C_camera_stale.json")
        report = diagnose(snap, scenario="C_camera_stale")
        self.assertEqual(report["fault"], "CAMERA_STALE")
        self.assertEqual(report["proposed_action"]["name"], "restart_camera")
        self.assertEqual(report["route"]["selected"], "L1")

    def test_memory_on_skips_l2(self):
        snap = load_json(SCENARIO / "C_camera_stale.json")
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "episodes.json"
            shutil.copy2(FROZEN / "episodes_camera_stale.json", dest)
            store = EpisodeStore(dest)
            mem = Memory()
            mem.last_fire["CAMERA_STALE"] = mem.now()
            report = diagnose(snap, store=store, memory=mem, enable_memory=True, scenario="D_on")
        self.assertEqual(report["route"]["selected"], "MEM")
        self.assertEqual(report["proposed_action"]["name"], "restart_camera")
        self.assertFalse(report["l2"]["invoked_live"])
        self.assertFalse(report["l2"]["used_historical"])

    def test_memory_off_uses_historical_l2_only(self):
        snap = load_json(SCENARIO / "C_camera_stale.json")
        historical = load_json(FROZEN / "l2_camera_stale_historical.json")
        mem = Memory()
        mem.last_fire["CAMERA_STALE"] = mem.now()
        report = diagnose(
            snap,
            memory=mem,
            enable_memory=False,
            historical_l2=historical,
            scenario="D_off",
            input_source="FROZEN REPLAY",
        )
        self.assertEqual(report["route"]["selected"], "L2")
        self.assertTrue(report["l2"]["used_historical"])
        self.assertFalse(report["l2"]["invoked_live"])
        self.assertIn("HISTORICAL", report["l2"]["note"])

    def test_frozen_episode_file_unchanged_by_suggest(self):
        path = FROZEN / "episodes_camera_stale.json"
        before = path.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "episodes.json"
            shutil.copy2(path, dest)
            store = EpisodeStore(dest)
            self.assertIsNotNone(store.suggest("CAMERA_STALE"))
        after = path.read_text(encoding="utf-8")
        self.assertEqual(before, after)

    def test_v2_specialists_normalized_for_policy(self):
        snap = load_json(SCENARIO / "A_healthy.json")
        norm = normalize_snapshot(snap)
        self.assertIn("scratch_v5", norm)
        self.assertEqual(classify_fault(norm), None)

    def test_live_l2_proposal_marked_live_not_executed(self):
        snap = load_json(SCENARIO / "C_camera_stale.json")
        mem = Memory()
        mem.last_fire["CAMERA_STALE"] = mem.now()
        report = diagnose(
            snap,
            memory=mem,
            enable_memory=False,
            live_l2_proposal={"tool": "restart_camera", "params": {}},
            live_l2_meta={"latency_s": 1.2, "note": "LIVE INFERENCE (proposal only; not executed)"},
            scenario="E_live_sim",
            input_source="LIVE GET /api/state",
        )
        self.assertEqual(report["route"]["selected"], "L2")
        self.assertTrue(report["l2"]["invoked_live"])
        self.assertFalse(report["actually_executed"])
        self.assertFalse(report["recovery_claimed"])
        self.assertIn("LIVE", report["l2"]["note"])


class DemoCliSafetyTests(unittest.TestCase):
    def test_demo_module_never_imports_mutating_runtime_loop(self):
        import tools.agent_midterm_demo as demo

        self.assertFalse(hasattr(demo, "run_loop"))
        report = demo.run_scenario("A_healthy", out_dir=None)
        self.assertFalse(report["actually_executed"])
        self.assertTrue(report["ACTUAL_EXECUTION_DISABLED"])
        client = ReadOnlyControlClient(snapshot={})
        with self.assertRaises(ObserveOnlyViolation):
            client.post_action("restart_worker", {})


if __name__ == "__main__":
    unittest.main()
