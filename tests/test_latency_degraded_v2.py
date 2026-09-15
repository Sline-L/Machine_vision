"""Tests for LATENCY_DEGRADED_V2 engineering + fail-closed formal gate."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gp.actions import _pre_set_profile
from gp.capability_registry import (
    CapabilityError,
    assert_switchable,
    is_runtime_available,
    load_registry,
)
from gp.capability_v2 import (
    PROFILE_ID,
    CapabilityArtifactError,
    capability_identity_from_runtime,
    load_frozen,
    validate_frozen_artifacts,
)
from gp.config import AppConfig, PROJECT_ROOT
from gp.profiles import ProfileError, SPECS, apply_to_config, available_capabilities
from gp.scratch_v5 import fuse_single_classifier, load_model2_config


class LatencyDegradedV2Tests(unittest.TestCase):
    def test_frozen_artifact_hash_and_weights(self):
        frozen = load_frozen()
        self.assertEqual(frozen["profile_id"], PROFILE_ID)
        self.assertFalse(frozen["mission_approved"])
        self.assertEqual(frozen["formal_holdout_status"], "MISSING")
        identity = validate_frozen_artifacts(frozen)
        self.assertEqual(identity["config_hash"], frozen["config_hash"])
        self.assertEqual(len(identity["classifier_sha"]), 64)

    def test_registry_implemented_not_available(self):
        self.assertFalse(is_runtime_available(PROFILE_ID))
        row = next(r for r in available_capabilities() if r["profile_id"] == PROFILE_ID)
        self.assertTrue(row["implemented"])
        self.assertFalse(row["mission_approved"])
        self.assertFalse(row["available"])
        self.assertEqual(row["status"], "ENGINEERING_IMPLEMENTED")

    def test_production_request_rejected(self):
        config = AppConfig()
        with self.assertRaises(ProfileError):
            apply_to_config(config, PROFILE_ID, engineering_mode=False)
        self.assertEqual(config.inference_profile, "FULL")
        ok, message = _pre_set_profile({"profile": PROFILE_ID}, {}, {})
        self.assertFalse(ok)
        self.assertIn("registry", message)

    def test_engineering_load_and_rollback_topology(self):
        config = AppConfig()
        plan = apply_to_config(config, PROFILE_ID, engineering_mode=True)
        self.assertTrue(plan["rebuild_inspector"])
        self.assertEqual(config.inference_profile, PROFILE_ID)
        self.assertAlmostEqual(config.defect_threshold, 0.2653394325872992)
        v2 = capability_identity_from_runtime(config.model2_config, config.defect_threshold)
        self.assertTrue(v2["matches_latency_degraded_v2"])
        self.assertEqual(v2["classifier_count"], 1)
        self.assertFalse(v2["matches_full_scratch_v5"])

        back = apply_to_config(config, "FULL", engineering_mode=True)
        self.assertTrue(back["rebuild_inspector"])
        full = capability_identity_from_runtime(config.model2_config, config.defect_threshold)
        self.assertTrue(full["matches_full_scratch_v5"])
        self.assertEqual(full["classifier_count"], 2)
        self.assertAlmostEqual(config.defect_threshold, 0.300273610279458)

    def test_sparse_startup_still_works(self):
        config = AppConfig()
        apply_to_config(config, "SPARSE")
        self.assertEqual(config.inference_profile, "SPARSE")
        apply_to_config(config, "FULL")
        self.assertEqual(config.inference_profile, "FULL")

    def test_leaving_v2_via_sparse_restores_full_scratch(self):
        config = AppConfig()
        apply_to_config(config, PROFILE_ID, engineering_mode=True)
        apply_to_config(config, "SPARSE", engineering_mode=True)
        self.assertEqual(config.inference_profile, "SPARSE")
        full = capability_identity_from_runtime(config.model2_config, config.defect_threshold)
        self.assertTrue(full["matches_full_scratch_v5"])

    def test_bad_classifier_sha_reject(self):
        frozen = load_frozen()
        frozen = dict(frozen)
        frozen["classifier"] = dict(frozen["classifier"])
        frozen["classifier"]["sha256"] = "0" * 64
        with self.assertRaises(CapabilityArtifactError) as ctx:
            validate_frozen_artifacts(frozen)
        self.assertEqual(ctx.exception.reason, "CAPABILITY_HASH_MISMATCH")

    def test_bad_detector_sha_reject(self):
        frozen = load_frozen()
        frozen = dict(frozen)
        frozen["detector"] = dict(frozen["detector"])
        frozen["detector"]["sha256"] = "1" * 64
        with self.assertRaises(CapabilityArtifactError) as ctx:
            validate_frozen_artifacts(frozen)
        self.assertEqual(ctx.exception.reason, "CAPABILITY_HASH_MISMATCH")

    def test_missing_artifact_reject(self):
        with patch("gp.capability_v2.V2_INFERENCE_CONFIG", Path("/nonexistent/v2.json")):
            with self.assertRaises(CapabilityArtifactError) as ctx:
                validate_frozen_artifacts()
            self.assertEqual(ctx.exception.reason, "CAPABILITY_ARTIFACT_MISSING")

    def test_v2_inference_config_loads(self):
        path = PROJECT_ROOT / "model/model2/profiles/latency_degraded_v2/inference_config.json"
        cfg = load_model2_config(path, verify_hashes=True)
        self.assertEqual(cfg["version"], "scratch_v5_latency_degraded_v2")
        self.assertEqual(len(cfg["classifiers"]), 1)

    def test_fuse_single(self):
        fused, cls = fuse_single_classifier(0.8, 0.4, alpha=0.25)
        self.assertAlmostEqual(fused, 0.25 * 0.8 + 0.75 * 0.4)
        self.assertAlmostEqual(cls, 0.8)

    def test_engineering_assert_switchable_skips_mission(self):
        assert_switchable(PROFILE_ID, legacy_implemented=True, engineering_mode=True)
        with self.assertRaises(CapabilityError):
            assert_switchable(PROFILE_ID, legacy_implemented=True, engineering_mode=False)

    def test_idempotent_full_to_full(self):
        config = AppConfig()
        apply_to_config(config, "FULL")
        apply_to_config(config, "FULL")
        self.assertEqual(config.inference_profile, "FULL")

    def test_holdout_seal_and_validate_roundtrip(self):
        from tools.holdout.seal_holdout import seal_holdout
        from tools.holdout.validate_holdout_manifest import validate_manifest

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = root / "images"
            images.mkdir()
            (images / "a.jpg").write_bytes(b"fake-image-a")
            (images / "b.jpg").write_bytes(b"fake-image-b")
            labels = root / "labels.json"
            labels.write_text(json.dumps({"a.jpg": "scratch", "b.jpg": "normal"}), encoding="utf-8")
            manifest_path = root / "manifest.json"
            sealed = seal_holdout(
                images,
                labels,
                dataset_id="unit-holdout",
                source_description="unit test",
                output=manifest_path,
            )
            report = validate_manifest(manifest_path)
            self.assertTrue(report["ok"])
            self.assertEqual(report["dataset_sha256"], sealed["dataset_sha256"])
            # Tamper
            (images / "a.jpg").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                validate_manifest(manifest_path)

    def test_formal_evaluator_one_shot_lock(self):
        from tools.holdout.formal_evaluate_capability import formal_evaluate
        from tools.holdout.seal_holdout import seal_holdout

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = root / "images"
            images.mkdir()
            files = []
            for i in range(4):
                name = f"img{i}.jpg"
                (images / name).write_bytes(f"img-{i}".encode())
                files.append(name)
            labels = {
                files[0]: "scratch",
                files[1]: "scratch",
                files[2]: "normal",
                files[3]: "normal",
            }
            labels_path = root / "labels.json"
            labels_path.write_text(json.dumps(labels), encoding="utf-8")
            manifest_path = root / "manifest.json"
            seal_holdout(
                images,
                labels_path,
                dataset_id="unit-formal",
                source_description="unit",
                output=manifest_path,
            )
            pred = root / "pred.csv"
            # High scores on scratch, low on normal → Q_D high for unit smoke
            pred.write_text(
                "file,score\n"
                f"{files[0]},0.9\n{files[1]},0.95\n{files[2]},0.1\n{files[3]},0.05\n",
                encoding="utf-8",
            )
            out = root / "out"
            first = formal_evaluate(
                holdout_manifest=manifest_path,
                predictions_csv=pred,
                out_dir=out,
                diagnostic_only=False,
            )
            self.assertTrue((out / "evaluation_lock.json").is_file())
            self.assertTrue(first["mission_contract_pass"])
            with self.assertRaises(RuntimeError):
                formal_evaluate(
                    holdout_manifest=manifest_path,
                    predictions_csv=pred,
                    out_dir=out,
                    diagnostic_only=False,
                )
            # diagnostic still allowed
            diag = formal_evaluate(
                holdout_manifest=manifest_path,
                predictions_csv=pred,
                out_dir=out,
                diagnostic_only=True,
            )
            self.assertEqual(diag["mode"], "DIAGNOSTIC_ONLY")

    def test_specs_contains_v2(self):
        self.assertIn(PROFILE_ID, SPECS)
        self.assertTrue(SPECS[PROFILE_ID]["implemented"])
        self.assertEqual(SPECS[PROFILE_ID]["applicability"], ["V5_OVERLOAD"])


if __name__ == "__main__":
    unittest.main()
