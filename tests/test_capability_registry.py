import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gp.capability_registry import (
    assert_switchable,
    CapabilityError,
    is_runtime_available,
    list_profile_availability,
    load_registry,
)
from gp.config import AppConfig
from gp.profiles import ProfileError, SPECS, apply_to_config, available_capabilities


class CapabilityRegistryTests(unittest.TestCase):
    def test_full_and_sparse_remain_available(self):
        self.assertTrue(is_runtime_available("FULL"))
        self.assertTrue(is_runtime_available("SPARSE"))
        config = AppConfig()
        apply_to_config(config, "SPARSE")
        self.assertEqual(config.inference_profile, "SPARSE")
        apply_to_config(config, "FULL")
        self.assertEqual(config.inference_profile, "FULL")

    def test_rejected_classifier_only_v1_not_available(self):
        self.assertFalse(is_runtime_available("classifier_only_v1"))
        with self.assertRaises(CapabilityError):
            assert_switchable("classifier_only_v1", legacy_implemented=True)

    def test_classify_only_still_unimplemented(self):
        config = AppConfig()
        with self.assertRaises(ProfileError):
            apply_to_config(config, "CLASSIFY_ONLY")
        self.assertEqual(config.inference_profile, "FULL")
        row = next(r for r in available_capabilities() if r["profile_id"] == "CLASSIFY_ONLY")
        self.assertFalse(row["available"])
        self.assertFalse(row["mission_approved"])

    def test_client_cannot_spoof_approval_via_temp_registry(self):
        payload = {
            "schema_version": "capability-registry.v1",
            "fail_closed": True,
            "capabilities": [
                {
                    "profile_id": "CLASSIFY_ONLY",
                    "status": "REJECTED",
                    "implemented": True,
                    "mission_approved": True,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "registry.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            load_registry(path, reload=True)
            # REJECTED wins even if flags claim true
            self.assertFalse(is_runtime_available("CLASSIFY_ONLY", path))
            with self.assertRaises(CapabilityError):
                assert_switchable("CLASSIFY_ONLY", legacy_implemented=True, path=path)
            # restore default cache for other tests
            load_registry(reload=True)

    def test_availability_list_includes_registry_only_ids(self):
        rows = {r["profile_id"]: r for r in list_profile_availability(SPECS)}
        self.assertIn("classifier_only_v1", rows)
        self.assertFalse(rows["classifier_only_v1"]["available"])
        self.assertEqual(rows["classifier_only_v1"]["status"], "REJECTED")
        self.assertTrue(rows["FULL"]["available"])


if __name__ == "__main__":
    unittest.main()
