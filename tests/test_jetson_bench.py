import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from gp.bench import (
    build_parser,
    compare_predictions,
    describe,
    detection_metrics,
    load_labels,
    percentile,
)
from gp.config import PROJECT_ROOT
from gp.power_monitor import energy_joules, parse_nvidia_smi_line, parse_tegrastats_line, window
from gp.specialist_engines import MANIFEST_SCHEMA, bundle_models, verify_manifest

HAS_TORCH = importlib.util.find_spec("torch") is not None and importlib.util.find_spec("cv2") is not None

# Representative Orin-style line (format per tegrastats documentation, not a recorded measurement).
ORIN_LINE = (
    "10-08-2026 10:00:00 RAM 5120/15388MB (lfb 2x4MB) SWAP 0/7694MB (cached 0MB) "
    "CPU [12%@1984,8%@1984,off,off,5%@1984,3%@1984,0%@1984,1%@1984] EMC_FREQ 21%@3199 "
    "GR3D_FREQ 63%@[918,918] NVENC off NVDEC off NVJPG off NVJPG1 off VIC off OFA off "
    "NVDLA0 off NVDLA1 1600 PVA0_FREQ off APE 174 cpu@52.5C soc2@49.1C soc0@50.2C gpu@53.8C "
    "tj@53.8C soc1@49.9C VDD_IN 12345mW/11000mW VDD_CPU_GPU_CV 5200mW/4800mW VDD_SOC 2500mW/2400mW"
)


class PowerParsingTests(unittest.TestCase):
    def test_tegrastats_orin_line(self):
        sample = parse_tegrastats_line(ORIN_LINE)
        self.assertEqual(sample["ram_used_mb"], 5120)
        self.assertEqual(sample["gpu_util_pct"], 63)
        self.assertEqual(sample["emc_util_pct"], 21)
        self.assertAlmostEqual(sample["cpu_util_pct"], (12 + 8 + 5 + 3 + 0 + 1) / 6)
        self.assertEqual(sample["nvdla0_active"], 0.0)
        self.assertEqual(sample["nvdla1_active"], 1.0)
        self.assertAlmostEqual(sample["temp_gpu_c"], 53.8)
        self.assertAlmostEqual(sample["vdd_in_w"], 12.345)
        self.assertAlmostEqual(sample["vdd_cpu_gpu_cv_w"], 5.2)
        self.assertAlmostEqual(sample["power_w"], 12.345)
        self.assertNotIn("temp_1984_c", sample)

    def test_tegrastats_documented_dla_forms(self):
        sample = parse_tegrastats_line("NVDLA0 25%@614 NVDLA1 1600 GR3D_FREQ 1%")
        self.assertEqual(sample["nvdla0_util_pct"], 25)
        self.assertEqual(sample["nvdla0_mhz"], 614)
        self.assertEqual(sample["nvdla1_active"], 1.0)
        self.assertEqual(sample["nvdla1_mhz"], 1600)
        self.assertNotIn("nvdla1_util_pct", sample)
        self.assertEqual(parse_tegrastats_line("NVDLA0 40% RAM 1/2MB")["nvdla0_util_pct"], 40)

    def test_tegrastats_legacy_rail_format(self):
        sample = parse_tegrastats_line("RAM 100/200MB VDD_IN 4870/4870 GR3D_FREQ 0%@305")
        self.assertAlmostEqual(sample["power_w"], 4.87)

    def test_nvidia_smi_line_skips_unsupported(self):
        sample = parse_nvidia_smi_line("35.50, 87, 2345, 61, [N/A]")
        self.assertEqual(sample, {"power_w": 35.5, "gpu_util_pct": 87, "gpu_mem_mb": 2345, "temp_gpu_c": 61})

    def test_energy_is_trapezoidal_within_window(self):
        samples = [{"t": 0.0, "power_w": 10.0}, {"t": 1.0, "power_w": 12.0}, {"t": 2.0, "power_w": 12.0}]
        self.assertAlmostEqual(energy_joules(samples), 23.0)
        self.assertEqual(len(window(samples, 0.5, 2.0)), 2)


class StatisticsTests(unittest.TestCase):
    def test_percentile_matches_linear_interpolation(self):
        values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        self.assertAlmostEqual(percentile(values, 50), 5.5)
        self.assertAlmostEqual(percentile(values, 95), 9.55)
        self.assertIsNone(percentile([], 50))
        self.assertEqual(describe([None, 4.0])["p95"], 4.0)

    def test_labels_and_detection_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "labels.csv"
            path.write_text(
                "image,scratch,missing_hole\na.jpg,1,0\nb.jpg,0,0\nc.jpg,0,1\nd.jpg,,0\n",
                encoding="utf-8",
            )
            labels = load_labels(path)
        self.assertEqual(labels["a.jpg"]["part"], "1")
        self.assertEqual(labels["b.jpg"]["part"], "0")
        self.assertEqual(labels["d.jpg"]["part"], "")
        rows = [
            {"label_part": "1", "part_reject": 1},
            {"label_part": "0", "part_reject": 1},
            {"label_part": "1", "part_reject": 0},
            {"label_part": "", "part_reject": 1},
        ]
        metrics = detection_metrics(rows, "part")
        self.assertEqual((metrics["tp"], metrics["fn"], metrics["fp"], metrics["tn"]), (1, 1, 1, 0))
        self.assertAlmostEqual(metrics["p_d"], 0.5)
        self.assertAlmostEqual(metrics["p_fa"], 1.0)

    def test_bench_parser_has_three_commands(self):
        parser = build_parser()
        args = parser.parse_args(["run", "--images", "x", "--tag", "nx-pt"])
        self.assertEqual(args.input, "frame")
        self.assertFalse(args.overlap)
        self.assertEqual(parser.parse_args(["compare", "a", "b"]).max_score_delta, 0.02)


def _row(image, scratch, missing, label_scratch="", label_missing=""):
    scratch_reject = int(scratch >= 0.3)
    missing_reject = int(missing >= 0.34)
    part = "1" if "1" in (label_scratch, label_missing) else ("0" if label_scratch == label_missing == "0" else "")
    return {
        "image": image,
        "gears": "1",
        "scratch_score": str(scratch),
        "scratch_reject": str(scratch_reject),
        "missing_hole_score": str(missing),
        "missing_hole_reject": str(missing_reject),
        "part_reject": str(int(scratch_reject or missing_reject)),
        "label_scratch": label_scratch,
        "label_missing_hole": label_missing,
        "label_part": part,
    }


class ParityTests(unittest.TestCase):
    thresholds = {"scratch": 0.3, "missing_hole": 0.34}

    def reference(self):
        return [
            _row("a", 0.90, 0.10, "1", "0"),
            _row("b", 0.10, 0.10, "0", "0"),
            _row("c", 0.295, 0.10, "0", "0"),
            _row("d", 0.10, 0.80, "0", "1"),
        ]

    def test_identical_runs_pass(self):
        result = compare_predictions(self.reference(), self.reference(), self.thresholds)
        self.assertTrue(result["passed"], result["checks"])

    def test_boundary_flip_within_budget_passes_but_reports(self):
        candidate = self.reference()
        candidate[2] = _row("c", 0.305, 0.10, "0", "0")
        result = compare_predictions(self.reference(), candidate, self.thresholds)
        self.assertEqual(result["subsystems"]["scratch"]["flips"], ["c"])
        self.assertTrue(result["passed"], result["checks"])

    def test_far_from_threshold_flip_fails(self):
        candidate = self.reference()
        candidate[1] = _row("b", 0.45, 0.10, "0", "0")
        result = compare_predictions(self.reference(), candidate, self.thresholds, {"max_score_delta": 1.0, "mean_score_delta": 1.0})
        failed = {item["check"] for item in result["checks"] if not item["passed"]}
        self.assertIn("scratch_flips", failed)

    def test_new_missed_defect_fails(self):
        candidate = self.reference()
        candidate[0] = _row("a", 0.29, 0.10, "1", "0")
        result = compare_predictions(self.reference(), candidate, self.thresholds, {"max_score_delta": 1.0, "mean_score_delta": 1.0, "boundary": 1.0})
        failed = {item["check"] for item in result["checks"] if not item["passed"]}
        self.assertIn("part_no_new_misses", failed)
        self.assertFalse(result["passed"])

    def test_gear_count_mismatch_fails(self):
        candidate = self.reference()
        candidate[3] = dict(candidate[3], gears="0")
        result = compare_predictions(self.reference(), candidate, self.thresholds)
        self.assertFalse(result["passed"])


class EngineManifestTests(unittest.TestCase):
    def make_bundle(self, directory):
        directory = Path(directory)
        config = {
            "version": "scratch_v5",
            "classifiers": [
                {"name": "one", "sha256": "a" * 64, "imgsz": 384},
                {"name": "two", "sha256": "b" * 64, "imgsz": 384},
            ],
            "detector": {"name": "det", "sha256": "c" * 64, "imgsz": 960},
        }
        models = {}
        for item, kind in bundle_models(config):
            payload = f"engine-{item['name']}".encode()
            (directory / f"{item['name']}.engine").write_bytes(payload)
            models[item["name"]] = {
                "kind": kind,
                "source_sha256": item["sha256"],
                "imgsz": item["imgsz"],
                "engine_sha256": hashlib.sha256(payload).hexdigest(),
                "dla_core": None,
            }
        manifest = {"schema": MANIFEST_SCHEMA, "bundle_version": "scratch_v5", "tensorrt": "10.3.0", "models": models}
        (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return config

    def test_valid_manifest_binds_engines_to_pt_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            config = self.make_bundle(directory)
            entries = verify_manifest(directory, config, tensorrt_version="10.3.0")
        self.assertEqual(set(entries), {"one", "two", "det"})

    def test_retrained_pt_rejects_stale_engine(self):
        with tempfile.TemporaryDirectory() as directory:
            config = self.make_bundle(directory)
            config["classifiers"][0]["sha256"] = "d" * 64
            with self.assertRaisesRegex(ValueError, "重新导出"):
                verify_manifest(directory, config)

    def test_tensorrt_version_and_engine_hash_are_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            config = self.make_bundle(directory)
            with self.assertRaisesRegex(ValueError, "TensorRT"):
                verify_manifest(directory, config, tensorrt_version="8.6.2")
            (Path(directory) / "det.engine").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "校验失败"):
                verify_manifest(directory, config)


@unittest.skipUnless(HAS_TORCH, "需要 torch / OpenCV")
class SharedPreprocessTests(unittest.TestCase):
    def test_shared_preprocess_gives_identical_scores(self):
        import numpy as np

        from gp.scratch_v5 import ScratchV5Runtime

        runtime = ScratchV5Runtime(PROJECT_ROOT / "model" / "model2" / "inference_config.json", device="cpu", warmup=False)
        rng = np.random.default_rng(0)
        crop = rng.integers(0, 255, (300, 280, 3), dtype=np.uint8)
        # The first CPU call after loading differs at ~1e-9 (backend algorithm warm-up).
        runtime.predict(crop)
        plain = runtime.predict(crop)
        shared = {}
        reused = runtime.predict(crop, shared)
        self.assertEqual(plain.defect_score, reused.defect_score)
        self.assertEqual(plain.classifier_probability, reused.classifier_probability)
        # Both Scratch V5 classifiers use 384, so one tensor serves both.
        self.assertEqual(sorted(key for key in shared if key != "rgb"), [("tensor", 384)])

    def test_overlap_requires_engines(self):
        from gp.scratch_v5 import ScratchV5Runtime

        with self.assertRaisesRegex(ValueError, "engine"):
            ScratchV5Runtime(
                PROJECT_ROOT / "model" / "model2" / "inference_config.json",
                device="cpu",
                warmup=False,
                overlap=True,
            )


if __name__ == "__main__":
    unittest.main()
