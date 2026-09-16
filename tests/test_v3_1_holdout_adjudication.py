"""V3-1 holdout adjudication infrastructure tests. Never reads fresh holdout."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from v3_fp_veto.adjudication import adjudicate
from v3_fp_veto.frozen_inference import (
    CANDIDATE_COMMIT,
    EXPECTED_FEATURE_NAMES,
    V3_1_THRESHOLD,
    apply_veto_to_feature_row,
    load_frozen_veto,
    load_full_threshold,
    load_v2_threshold,
)
from v3_fp_veto.metrics import classification_metrics
from v3_fp_veto.seal_fresh_holdout import seal_fresh_holdout


def _metrics(tp, fp, tn, fn):
    n = tp + fp + tn + fn
    y_true = [1] * (tp + fn) + [0] * (fp + tn)
    y_pred = [1] * tp + [0] * fn + [1] * fp + [0] * tn
    return classification_metrics(y_true, y_pred)


class FrozenVetoTests(unittest.TestCase):
    def test_candidate_commit_lock(self):
        self.assertEqual(CANDIDATE_COMMIT, "e8b2b0fda2af2c9c8c697d4655d527947381377a")

    def test_v2_threshold_from_freeze_artifact(self):
        thr = load_v2_threshold()
        self.assertAlmostEqual(thr, 0.2653394325872992)
        frozen = json.loads(
            (ROOT / "docs/capability-extraction/v3/latency_degraded_v2_effnet_det.frozen.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertAlmostEqual(thr, float(frozen["threshold"]))

    def test_full_threshold_from_full_config(self):
        self.assertAlmostEqual(load_full_threshold(), 0.300273610279458)

    def test_feature_order_matches_artifact(self):
        veto = load_frozen_veto()
        self.assertEqual(list(veto.feature_names), EXPECTED_FEATURE_NAMES)
        self.assertEqual(veto.threshold, V3_1_THRESHOLD)
        self.assertEqual(veto.mode, "replace_score")

    def test_nx_s1_imports_same_primitives(self):
        spec = importlib.util.spec_from_file_location(
            "nx_s1_paired_latency",
            ROOT / "tools/v3_fp_veto/nx_s1_paired_latency.py",
        )
        module = importlib.util.module_from_spec(spec)
        # Avoid executing NX injector imports: only check source text.
        source = (ROOT / "tools/v3_fp_veto/nx_s1_paired_latency.py").read_text(encoding="utf-8")
        self.assertIn("from v3_fp_veto.frozen_inference import backbone_features, load_veto", source)
        self.assertNotIn("def load_veto", source)
        self.assertNotIn("def backbone_features", source)
        self.assertIsNotNone(spec)

    def test_formal_script_does_not_import_train_pareto(self):
        source = (ROOT / "tools/v3_fp_veto/formal_fresh_holdout_adjudicate.py").read_text(encoding="utf-8")
        self.assertNotIn("import train_pareto", source)
        self.assertNotIn("from train_pareto", source)
        self.assertNotIn("from v3_fp_veto.train_pareto", source)
        extract = (ROOT / "tools/v3_fp_veto/extract_features.py").read_text(encoding="utf-8")
        self.assertIn("holdout", extract)
        self.assertIn("refusing split", extract)

    def test_val_features_reproduce_freeze_v3_1_counts(self):
        veto = load_frozen_veto()
        v2_thr = load_v2_threshold()
        path = ROOT / "docs/capability-extraction/v3/v3-1-fp-veto/features_train_val.csv"
        rows = [r for r in csv.DictReader(path.open(encoding="utf-8")) if r["split"] == "val_scratch"]
        self.assertEqual(len(rows), 150)
        y_true = [int(r["label"]) for r in rows]
        y_v2 = [int(r["v2_reject"]) for r in rows]
        y_v31 = []
        for row in rows:
            applied = apply_veto_to_feature_row(row, veto, v2_threshold=v2_thr)
            y_v31.append(applied["prediction"])
            np.testing.assert_allclose(
                applied["feature_vector"],
                [float(row[n]) for n in EXPECTED_FEATURE_NAMES],
            )
        m_v2 = classification_metrics(y_true, y_v2)
        m_v31 = classification_metrics(y_true, y_v31)
        self.assertEqual((m_v2["tp"], m_v2["fp"], m_v2["tn"], m_v2["fn"]), (42, 12, 95, 1))
        self.assertEqual((m_v31["tp"], m_v31["fp"], m_v31["tn"], m_v31["fn"]), (40, 6, 101, 3))
        self.assertAlmostEqual(m_v31["Q_D"], 0.9302325581395349)
        self.assertAlmostEqual(m_v31["fpr"], 0.056074766355140186)
        self.assertAlmostEqual(m_v31["recall"], 0.9302325581395349)

    def test_shuffled_feature_order_changes_probability(self):
        veto = load_frozen_veto()
        path = ROOT / "docs/capability-extraction/v3/v3-1-fp-veto/features_train_val.csv"
        row = next(r for r in csv.DictReader(path.open(encoding="utf-8")) if r["split"] == "val_scratch")
        feat = {n: float(row[n]) for n in EXPECTED_FEATURE_NAMES}
        p0 = veto.predict_proba(feat)
        swapped = dict(feat)
        swapped["cls1"], swapped["raw_det"] = swapped["raw_det"], swapped["cls1"]
        p1 = veto.predict_proba(swapped)
        self.assertNotAlmostEqual(p0, p1)


class AdjudicationRuleTests(unittest.TestCase):
    def test_pass(self):
        v2 = _metrics(85, 20, 80, 15)  # R=0.85 FPR=0.20 Q_D=0.80
        v31 = _metrics(84, 10, 90, 16)  # R=0.84 FPR=0.10 Q_D=0.84
        full = _metrics(92, 4, 96, 8)
        out = adjudicate(metrics_full=full, metrics_v2=v2, metrics_v3_1=v31, per_sample_rows=[])
        self.assertTrue(out["pass_conditions"]["FPR_reduction"]["pass"])
        self.assertEqual(out["overall"], "PASS")
        self.assertFalse(any(out["failure_flags"].values()))

    def test_fail_a_recall_drop(self):
        v2 = _metrics(95, 20, 80, 5)
        v31 = _metrics(80, 5, 95, 20)  # recall drop 0.15
        full = _metrics(96, 4, 96, 4)
        out = adjudicate(metrics_full=full, metrics_v2=v2, metrics_v3_1=v31, per_sample_rows=[])
        self.assertTrue(out["failure_flags"]["FAIL_A"])
        self.assertEqual(out["overall"], "FAIL")

    def test_fail_b_fpr(self):
        v2 = _metrics(90, 10, 90, 10)
        v31 = _metrics(90, 9, 91, 10)  # FPR drop 0.01
        full = _metrics(92, 4, 96, 8)
        out = adjudicate(metrics_full=full, metrics_v2=v2, metrics_v3_1=v31, per_sample_rows=[])
        self.assertTrue(out["failure_flags"]["FAIL_B"])
        self.assertEqual(out["overall"], "FAIL")

    def test_fail_c(self):
        v2 = _metrics(70, 40, 60, 30)
        v31 = _metrics(65, 20, 80, 35)
        full = _metrics(90, 5, 95, 10)
        out = adjudicate(metrics_full=full, metrics_v2=v2, metrics_v3_1=v31, per_sample_rows=[])
        self.assertTrue(out["failure_flags"]["FAIL_C"])
        self.assertEqual(out["overall"], "FAIL")

    def test_inconclusive_fpr_gray_zone(self):
        v2 = _metrics(92, 20, 80, 8)  # R=0.92 FPR=0.20 Q_D=0.80
        v31 = _metrics(90, 18, 82, 10)  # R=0.90 FPR=0.18 Q_D=0.82; FPR drop=0.02
        out = adjudicate(metrics_full=_metrics(92, 4, 96, 8), metrics_v2=v2, metrics_v3_1=v31, per_sample_rows=[])
        self.assertFalse(out["failure_flags"]["FAIL_B"])
        self.assertFalse(out["pass_conditions"]["FPR_reduction"]["pass"])
        self.assertEqual(out["overall"], "INCONCLUSIVE")

    def test_non_exclusive_flags(self):
        v2 = _metrics(95, 40, 60, 5)
        v31 = _metrics(70, 38, 62, 30)
        out = adjudicate(
            metrics_full=_metrics(96, 4, 96, 4),
            metrics_v2=v2,
            metrics_v3_1=v31,
            per_sample_rows=[],
        )
        self.assertTrue(out["failure_flags"]["FAIL_A"])
        self.assertTrue(out["failure_flags"]["FAIL_B"] or out["failure_flags"]["FAIL_C"])
        self.assertEqual(out["overall"], "FAIL")

    def test_easy_high_confidence_does_not_fail_a(self):
        rows = [
            {
                "ground_truth": 1,
                "full_prediction": 1,
                "v2_prediction": 1,
                "v3_1_prediction": 0,
            }
        ]
        v2 = _metrics(85, 20, 80, 15)
        v31 = _metrics(84, 10, 90, 16)
        out = adjudicate(metrics_full=_metrics(92, 4, 96, 8), metrics_v2=v2, metrics_v3_1=v31, per_sample_rows=rows)
        self.assertEqual(out["manual_review_flags"]["easy_high_confidence_fn"]["fn_on_easy_high_confidence_n"], 1)
        self.assertFalse(out["manual_review_flags"]["easy_high_confidence_fn"]["triggers_FAIL_A"])
        self.assertEqual(out["overall"], "PASS")


class SealAndLockTests(unittest.TestCase):
    def test_seal_and_persist_dry_run(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            images = tmp_path / "images"
            images.mkdir()
            Image.new("RGB", (8, 8), (12, 34, 56)).save(images / "a.png")
            Image.new("RGB", (8, 8), (70, 80, 90)).save(images / "b.png")
            labels = tmp_path / "labels.json"
            labels.write_text(json.dumps({"a.png": "scratch", "b.png": "normal"}), encoding="utf-8")
            out = tmp_path / "manifest.json"
            manifest = seal_fresh_holdout(
                images,
                labels,
                dataset_id="unit-fixture-not-holdout",
                source_description="synthetic unit fixture",
                output=out,
            )
            self.assertEqual(manifest["schema_version"], "scratch-holdout.v1")
            self.assertEqual(len(manifest["images"]), 2)
            self.assertTrue((tmp_path / "manifest.json.sha256").is_file())

            from v3_fp_veto.formal_fresh_holdout_adjudicate import run_from_feature_csv

            csv_path = ROOT / "docs/capability-extraction/v3/v3-1-fp-veto/features_train_val.csv"
            run_dir = tmp_path / "run"
            run_from_feature_csv(feature_csv=csv_path, out_dir=run_dir, split="val_scratch")
            for name in (
                "provenance.json",
                "per_sample_predictions.csv",
                "metrics_v2.json",
                "metrics_v3_1.json",
                "comparison.json",
                "adjudication.json",
                "evaluation_lock.json",
            ):
                self.assertTrue((run_dir / name).is_file(), name)
            adj = json.loads((run_dir / "adjudication.json").read_text(encoding="utf-8"))
            self.assertEqual(adj["candidate_commit"], CANDIDATE_COMMIT)
            self.assertEqual(adj["holdout_status"], "NOT_HOLDOUT")
            lock = json.loads((run_dir / "evaluation_lock.json").read_text(encoding="utf-8"))
            self.assertEqual(lock["status"], "DRY_RUN_COMPLETE")
            self.assertEqual(lock["holdout_status"], "NOT_HOLDOUT")

    def test_refuse_second_lock(self):
        from v3_fp_veto import formal_fresh_holdout_adjudicate as orch

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "evaluation_lock.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                orch.run_formal(holdout_manifest=out / "missing.json", out_dir=out)


if __name__ == "__main__":
    unittest.main()
