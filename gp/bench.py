"""Offline latency / power / accuracy-parity benchmark for the inspection pipeline.

    python -m gp.bench run --images DIR [--labels CSV] --tag nx-pt
    python -m gp.bench compare REF_RUN CANDIDATE_RUN
    python -m gp.bench report RUN [RUN ...]

`run` preloads images, warms up, then calls `TwoStageInspector.inspect`
back-to-back (no `inference_interval`), so throughput is pipeline capacity, not
camera cadence. Thresholds come from the bundle configs, never from
`var/settings.json`. Only measured values are written; missing sensors stay null.
See docs/jetson-acceleration.md for the protocol and acceptance criteria.
"""

import argparse
import csv
import datetime
import json
import math
from pathlib import Path
import platform
import subprocess
import sys
import time

from .config import PROJECT_ROOT, RUNTIME_ROOT, AppConfig

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
STAGES = (
    ("e2e_ms", None),
    ("locator_ms", "locator_latency_ms"),
    ("scratch_cls1_ms", "classifier1_latency_ms"),
    ("scratch_cls2_ms", "classifier2_latency_ms"),
    ("scratch_det_ms", "detector_latency_ms"),
    ("scratch_fuse_ms", "fusion_latency_ms"),
    ("scratch_ms", "scratch_latency_ms"),
    ("missing_cls1_ms", "missing_hole_classifier1_latency_ms"),
    ("missing_cls2_ms", "missing_hole_classifier2_latency_ms"),
    ("missing_det_ms", "missing_hole_detector_latency_ms"),
    ("missing_fuse_ms", "missing_hole_fusion_latency_ms"),
    ("missing_ms", "missing_hole_latency_ms"),
)
TARGETS = ("part", "scratch", "missing_hole")
DEFAULT_TOLERANCES = {
    "max_score_delta": 0.02,
    "mean_score_delta": 0.005,
    "boundary": 0.02,
    "max_flip_rate": 0.01,
    "extra_false_alarms": 1,
}


# ---------------------------------------------------------------- statistics


def percentile(values, q):
    """Linear-interpolated percentile (same convention as numpy's default)."""
    values = sorted(values)
    if not values:
        return None
    position = (len(values) - 1) * q / 100.0
    lower = math.floor(position)
    upper = math.ceil(position)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def describe(values):
    values = [float(value) for value in values if value is not None]
    if not values:
        return None
    mean = sum(values) / len(values)
    return {
        "n": len(values),
        "mean": mean,
        "std": math.sqrt(sum((value - mean) ** 2 for value in values) / len(values)),
        "min": min(values),
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
        "p99": percentile(values, 99),
        "max": max(values),
    }


def wilson_interval(successes, total, z=1.96):
    if total == 0:
        return None
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [max(0.0, centre - margin), min(1.0, centre + margin)]


def detection_metrics(rows, target):
    """P_D / P_FA for one target over rows with a known label."""
    tp = fn = fp = tn = 0
    for row in rows:
        label = row.get(f"label_{target}")
        if label in (None, ""):
            continue
        predicted = _truthy(row[f"{target}_reject"])
        if _truthy(label):
            tp += predicted
            fn += not predicted
        else:
            fp += predicted
            tn += not predicted
    positives, negatives = tp + fn, fp + tn
    return {
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "tn": tn,
        "p_d": tp / positives if positives else None,
        "p_d_ci95": wilson_interval(tp, positives),
        "p_fa": fp / negatives if negatives else None,
        "p_fa_ci95": wilson_interval(fp, negatives),
    }


def _truthy(value):
    return str(value).strip().lower() in {"1", "true", "yes"}


# ---------------------------------------------------------------- inputs


def list_images(directory):
    directory = Path(directory)
    return sorted(
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def load_labels(path):
    """CSV columns: image (relative path), scratch, missing_hole (1/0/blank)."""
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = {"image", "scratch", "missing_hole"} - set(reader.fieldnames or ())
        if missing:
            raise ValueError("标签 CSV 缺少列：" + "、".join(sorted(missing)))
        labels = {}
        for row in reader:
            values = {}
            for target in ("scratch", "missing_hole"):
                value = (row[target] or "").strip()
                if value not in ("", "0", "1"):
                    raise ValueError(f"{row['image']} 的 {target} 标签必须是 0、1 或留空")
                values[target] = value
            scratch, missing_hole = values["scratch"], values["missing_hole"]
            if "1" in (scratch, missing_hole):
                values["part"] = "1"
            elif scratch == missing_hole == "0":
                values["part"] = "0"
            else:
                values["part"] = ""
            labels[row["image"].replace("\\", "/")] = values
    return labels


# ---------------------------------------------------------------- provenance


def _command_output(command, timeout=5):
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = ((completed.stdout or "") + (completed.stderr or "")).strip()
    return text or None


def _read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").strip("\x00\n ")
    except OSError:
        return None


def environment_info():
    import torch

    info = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "python": platform.python_version(),
        "torch": torch.__version__,
        "torch_threads": torch.get_num_threads(),
        "cuda": torch.version.cuda,
        "cudnn": torch.backends.cudnn.version() if torch.backends.cudnn.is_available() else None,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "jetson_model": _read_text("/proc/device-tree/model"),
        "l4t_release": _read_text("/etc/nv_tegra_release"),
        "nvpmodel": _command_output(["nvpmodel", "-q"]),
        "jetson_clocks": _command_output(["jetson_clocks", "--show"]),
        "git_commit": _command_output(["git", "-C", str(PROJECT_ROOT), "rev-parse", "HEAD"]),
        "git_dirty": bool(_command_output(["git", "-C", str(PROJECT_ROOT), "status", "--porcelain"])),
    }
    try:
        import tensorrt

        info["tensorrt"] = tensorrt.__version__
    except ImportError:
        info["tensorrt"] = None
    try:
        import ultralytics

        info["ultralytics"] = ultralytics.__version__
    except ImportError:
        info["ultralytics"] = None
    return info


def peak_rss_mb():
    try:
        import resource

        # Linux reports ru_maxrss in KiB.
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except (ImportError, AttributeError):
        pass
    try:
        import psutil

        info = psutil.Process().memory_info()
        return getattr(info, "peak_wset", info.rss) / (1024 * 1024)
    except Exception:
        return None


# ---------------------------------------------------------------- run


def inspect_roi(inspector, image):
    """Score an image that already is a gear ROI (skips the locator)."""
    from .types import GearObservation, InspectionResult

    started = time.perf_counter()
    shared = {} if inspector.share_preprocess else None
    scratch = inspector.model2.predict(image, shared)
    missing = inspector.missing_hole.predict(image, shared)
    config = inspector.config
    height, width = image.shape[:2]
    observation = GearObservation(
        box=(0, 0, width, height),
        location_confidence=1.0,
        defect_score=scratch.defect_score,
        classifier_probability=scratch.classifier_probability,
        detector_probability=scratch.detector_probability,
        scratch_threshold=config.scratch_threshold,
        scratch_reject=scratch.defect_score >= config.scratch_threshold,
        missing_hole_probability=missing.probability,
        missing_hole_classifier_probability=missing.classifier_probability,
        missing_hole_detector_probability=missing.detector_probability,
        missing_hole_threshold=config.missing_hole_threshold,
        missing_hole_reject=missing.probability >= config.missing_hole_threshold,
    )
    scratch_ms = (
        scratch.classifier1_latency_ms + scratch.classifier2_latency_ms
        + scratch.detector_latency_ms + scratch.fusion_latency_ms
    )
    missing_ms = (
        missing.classifier1_latency_ms + missing.classifier2_latency_ms
        + missing.detector_latency_ms + missing.fusion_latency_ms
    )
    return InspectionResult(
        annotated_frame=None,
        observations=[observation],
        elapsed_ms=(time.perf_counter() - started) * 1000,
        classifier1_latency_ms=scratch.classifier1_latency_ms,
        classifier2_latency_ms=scratch.classifier2_latency_ms,
        detector_latency_ms=scratch.detector_latency_ms,
        fusion_latency_ms=scratch.fusion_latency_ms,
        scratch_latency_ms=scratch_ms,
        missing_hole_classifier1_latency_ms=missing.classifier1_latency_ms,
        missing_hole_classifier2_latency_ms=missing.classifier2_latency_ms,
        missing_hole_detector_latency_ms=missing.detector_latency_ms,
        missing_hole_fusion_latency_ms=missing.fusion_latency_ms,
        missing_hole_latency_ms=missing_ms,
    )


def prediction_row(image, result, labels):
    """Per-image summary; a subsystem rejects iff its max fused score >= threshold."""
    row = {"image": image, "gears": len(result.observations)}
    best_scratch = max(result.observations, key=lambda item: item.defect_score, default=None)
    best_missing = max(result.observations, key=lambda item: item.missing_hole_probability, default=None)
    row["scratch_score"] = None if best_scratch is None else best_scratch.defect_score
    row["scratch_classifier"] = None if best_scratch is None else best_scratch.classifier_probability
    row["scratch_detector"] = None if best_scratch is None else best_scratch.detector_probability
    row["scratch_reject"] = int(any(item.scratch_is_reject for item in result.observations))
    row["missing_hole_score"] = None if best_missing is None else best_missing.missing_hole_probability
    row["missing_hole_classifier"] = (
        None if best_missing is None else best_missing.missing_hole_classifier_probability
    )
    row["missing_hole_detector"] = None if best_missing is None else best_missing.missing_hole_detector_probability
    row["missing_hole_reject"] = int(any(item.missing_hole_reject for item in result.observations))
    row["part_reject"] = int(row["scratch_reject"] or row["missing_hole_reject"])
    label = labels.get(image, {})
    for target in TARGETS:
        row[f"label_{target}"] = label.get(target, "")
    return row


def _write_csv(path, rows):
    keys = []
    for row in rows:
        keys.extend(key for key in row if key not in keys)
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def _sample_summary(samples):
    keys = sorted({key for sample in samples for key in sample if key != "t"})
    summary = {}
    for key in keys:
        stats = describe(sample.get(key) for sample in samples)
        if stats:
            summary[key] = {"mean": stats["mean"], "p95": stats["p95"], "max": stats["max"], "n": stats["n"]}
    return summary


def power_summary(source, samples, idle_window, run_window, parts):
    from .power_monitor import energy_joules, window

    idle = window(samples, *idle_window)
    run = window(samples, *run_window)
    summary = {
        "source": source,
        "scope": "Jetson module input (VDD_IN)" if source == "tegrastats" else "discrete GPU board only",
        "idle": _sample_summary(idle),
        "run": _sample_summary(run),
        "energy_j": None,
        "energy_per_part_j": None,
        "dynamic_energy_per_part_j": None,
    }
    run_power = summary["run"].get("power_w")
    if run_power and len(run) > 1:
        duration = run_window[1] - run_window[0]
        summary["energy_j"] = energy_joules(run)
        if parts:
            summary["energy_per_part_j"] = run_power["mean"] * duration / parts
            idle_power = summary["idle"].get("power_w")
            if idle_power:
                summary["dynamic_energy_per_part_j"] = (run_power["mean"] - idle_power["mean"]) * duration / parts
    return summary


def bundle_threshold(path):
    return float(json.loads(Path(path).read_text(encoding="utf-8"))["default_threshold"])


def run_benchmark(args):
    import cv2
    import torch

    from .models import TwoStageInspector
    from .power_monitor import create_sampler
    from .specialist_engines import sha256_file

    images_dir = Path(args.images)
    labels = load_labels(args.labels) if args.labels else {}
    names = sorted(labels) if labels else list_images(images_dir)
    if not names:
        raise ValueError(f"没有可用图片：{images_dir}")
    frames = []
    for name in names:
        image = cv2.imread(str(images_dir / name), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"无法读取图片：{images_dir / name}")
        frames.append((name, image))

    device = args.device or ("cuda:0" if torch.cuda.is_available() else "cpu")
    cuda = device.startswith("cuda")
    config = AppConfig()
    if args.locator:
        config.locator_model = Path(args.locator)
    if args.model2:
        config.model2_config = Path(args.model2)
    if args.missing_hole:
        config.missing_hole_config = Path(args.missing_hole)
    config.scratch_threshold = bundle_threshold(config.model2_config)
    config.missing_hole_threshold = bundle_threshold(config.missing_hole_config)

    out = Path(args.out or RUNTIME_ROOT / "bench" / f"{args.tag}-{time.strftime('%Y%m%d-%H%M%S')}")
    out.mkdir(parents=True, exist_ok=True)
    sampler = create_sampler(args.power, args.sample_ms, cuda=cuda)
    if sampler is not None:
        sampler.start()
    try:
        load_started = time.monotonic()
        inspector = TwoStageInspector(
            config,
            device=device,
            engines=args.engines,
            overlap=args.overlap,
            share_preprocess=args.share_preprocess,
        )
        inspect = (lambda image: inspect_roi(inspector, image)) if args.input == "roi" else inspector.inspect
        for index in range(args.warmup):
            inspect(frames[index % len(frames)][1])
        if cuda:
            torch.cuda.synchronize()
        load_s = time.monotonic() - load_started

        idle_start = time.monotonic()
        time.sleep(args.idle_seconds)
        idle_end = time.monotonic()

        if cuda:
            torch.cuda.reset_peak_memory_stats()
        records, predictions, repeat_delta = [], {}, 0.0
        run_start = time.monotonic()
        passes = 0
        while passes < args.passes or time.monotonic() - run_start < args.min_seconds:
            for name, image in frames:
                started = time.perf_counter()
                result = inspect(image)
                if cuda:
                    torch.cuda.synchronize()
                record = {"pass": passes, "image": name, "e2e_ms": (time.perf_counter() - started) * 1000}
                for column, attribute in STAGES[1:]:
                    record[column] = getattr(result, attribute)
                record["gears"] = len(result.observations)
                records.append(record)
                row = prediction_row(name, result, labels)
                if passes == 0:
                    predictions[name] = row
                else:
                    first = predictions[name]
                    for key in ("scratch_score", "missing_hole_score"):
                        if first[key] is not None and row[key] is not None:
                            repeat_delta = max(repeat_delta, abs(first[key] - row[key]))
            passes += 1
        run_end = time.monotonic()
    finally:
        samples = sampler.stop() if sampler is not None else []

    parts = sum(record["gears"] for record in records)
    wall = run_end - run_start
    prediction_rows = [predictions[name] for name, _image in frames]
    summary = {
        "tag": args.tag,
        "note": args.note,
        "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "environment": environment_info(),
        "setup": {
            "device": device,
            "input": args.input,
            "images": str(images_dir.resolve()),
            "image_count": len(frames),
            "labels": None if not args.labels else str(Path(args.labels).resolve()),
            "labels_sha256": None if not args.labels else sha256_file(args.labels),
            "locator": str(Path(config.locator_model).resolve()),
            "locator_sha256": sha256_file(config.locator_model),
            "model2_config_sha256": sha256_file(config.model2_config),
            "missing_hole_config_sha256": sha256_file(config.missing_hole_config),
            "engines": None if not args.engines else str(Path(args.engines).resolve()),
            "engine_manifests": _engine_manifests(args.engines),
            "overlap": bool(args.overlap),
            "share_preprocess": bool(args.share_preprocess),
            "scratch_threshold": config.scratch_threshold,
            "missing_hole_threshold": config.missing_hole_threshold,
            "warmup_frames": args.warmup,
            "idle_seconds": args.idle_seconds,
        },
        "timing": {
            "load_and_warmup_s": load_s,
            "passes": passes,
            "frames": len(records),
            "parts": parts,
            "wall_s": wall,
            "frames_per_s": len(records) / wall if wall else None,
            "parts_per_s": parts / wall if wall else None,
            "repeat_max_score_delta": repeat_delta,
        },
        "latency_ms": {column: describe(record[column] for record in records) for column, _ in STAGES},
        "memory": {
            "torch_cuda_peak_mb": torch.cuda.max_memory_allocated() / (1024 * 1024) if cuda else None,
            "process_peak_rss_mb": peak_rss_mb(),
        },
        "power": None
        if sampler is None
        else power_summary(sampler.source, samples, (idle_start, idle_end), (run_start, run_end), parts),
        "accuracy": {target: detection_metrics(prediction_rows, target) for target in TARGETS} if labels else None,
        "no_gear_images": sum(1 for row in prediction_rows if row["gears"] == 0),
    }
    _write_csv(out / "frames.csv", records)
    _write_csv(out / "predictions.csv", prediction_rows)
    if samples:
        _write_csv(out / "power.csv", samples)
    if sampler is not None and sampler.raw_lines:
        # Keep raw sensor lines so runs can be re-parsed if field formats differ.
        (out / f"{sampler.source}.log").write_text("".join(sampler.raw_lines), encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out, summary


def _engine_manifests(engines):
    if not engines:
        return None
    manifests = {}
    for path in sorted(Path(engines).glob("*/manifest.json")):
        manifests[path.parent.name] = json.loads(path.read_text(encoding="utf-8"))
    return manifests


# ---------------------------------------------------------------- compare


def _read_csv(path):
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _float(value):
    return None if value in (None, "") else float(value)


def compare_predictions(reference, candidate, thresholds, tolerances=None):
    """Accuracy-parity checks of a candidate run against a reference run."""
    tolerances = {**DEFAULT_TOLERANCES, **(tolerances or {})}
    ref = {row["image"]: row for row in reference}
    cand = {row["image"]: row for row in candidate}
    checks = []

    def check(name, passed, detail):
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    check("same_images", set(ref) == set(cand), f"ref={len(ref)} cand={len(cand)}")
    common = sorted(set(ref) & set(cand))
    gear_mismatch = [image for image in common if ref[image]["gears"] != cand[image]["gears"]]
    check("same_gear_count", not gear_mismatch, f"{len(gear_mismatch)} 张定位数量不同 {gear_mismatch[:5]}")

    subsystems = {}
    allowed_flips = max(1, math.floor(tolerances["max_flip_rate"] * len(common)))
    for target, threshold in (("scratch", thresholds["scratch"]), ("missing_hole", thresholds["missing_hole"])):
        deltas, flips, unexplained = [], [], []
        for image in common:
            a, b = _float(ref[image][f"{target}_score"]), _float(cand[image][f"{target}_score"])
            if a is not None and b is not None:
                deltas.append(abs(a - b))
            if ref[image][f"{target}_reject"] != cand[image][f"{target}_reject"]:
                flips.append(image)
                if a is None or abs(a - threshold) > tolerances["boundary"]:
                    unexplained.append(image)
        stats = describe(deltas) or {"max": 0.0, "mean": 0.0}
        subsystems[target] = {"score_delta": describe(deltas), "flips": flips, "unexplained_flips": unexplained}
        check(f"{target}_max_score_delta", stats["max"] <= tolerances["max_score_delta"], f"max |Δ|={stats['max']:.5f}")
        check(f"{target}_mean_score_delta", stats["mean"] <= tolerances["mean_score_delta"], f"mean |Δ|={stats['mean']:.5f}")
        check(f"{target}_flips", len(flips) <= allowed_flips and not unexplained,
              f"{len(flips)} 翻转（允许 {allowed_flips}），阈值附近以外 {len(unexplained)}")
    part_flips = [image for image in common if ref[image]["part_reject"] != cand[image]["part_reject"]]
    check("part_flips", len(part_flips) <= allowed_flips, f"{len(part_flips)} 翻转（允许 {allowed_flips}）")

    accuracy = {}
    if any(row.get("label_part") not in (None, "") for row in reference):
        for target in TARGETS:
            a = detection_metrics([ref[image] for image in common], target)
            b = detection_metrics([cand[image] for image in common], target)
            accuracy[target] = {"reference": a, "candidate": b}
            check(f"{target}_no_new_misses", b["tp"] >= a["tp"], f"P_D {a['p_d']} → {b['p_d']}")
            check(
                f"{target}_false_alarms",
                b["fp"] <= a["fp"] + tolerances["extra_false_alarms"],
                f"P_FA {a['p_fa']} → {b['p_fa']}（FP {a['fp']} → {b['fp']}）",
            )
    return {
        "passed": all(item["passed"] for item in checks),
        "tolerances": tolerances,
        "checks": checks,
        "subsystems": subsystems,
        "part_flips": part_flips,
        "accuracy": accuracy,
    }


def compare_runs(reference_dir, candidate_dir, tolerances=None):
    reference_dir, candidate_dir = Path(reference_dir), Path(candidate_dir)
    ref_summary = json.loads((reference_dir / "summary.json").read_text(encoding="utf-8"))
    cand_summary = json.loads((candidate_dir / "summary.json").read_text(encoding="utf-8"))
    for key in ("scratch_threshold", "missing_hole_threshold", "labels_sha256", "image_count", "input"):
        if ref_summary["setup"].get(key) != cand_summary["setup"].get(key):
            raise ValueError(f"两次运行的 {key} 不同，不能比较精度")
    thresholds = {
        "scratch": ref_summary["setup"]["scratch_threshold"],
        "missing_hole": ref_summary["setup"]["missing_hole_threshold"],
    }
    result = compare_predictions(
        _read_csv(reference_dir / "predictions.csv"),
        _read_csv(candidate_dir / "predictions.csv"),
        thresholds,
        tolerances,
    )
    result["reference"] = str(reference_dir)
    result["candidate"] = str(candidate_dir)
    return result


# ---------------------------------------------------------------- report


def _fmt(value, digits=1):
    return "—" if value is None else f"{value:.{digits}f}"


def report_table(run_dirs):
    lines = [
        "| run | device | e2e p50 | e2e p95 | locator p95 | scratch p95 | missing p95 | parts/s"
        " | power mean W | J/part | dyn J/part | GPU % | T max °C |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for run_dir in run_dirs:
        summary = json.loads((Path(run_dir) / "summary.json").read_text(encoding="utf-8"))
        latency = summary["latency_ms"]
        p95 = lambda key: None if not latency.get(key) else latency[key]["p95"]
        power = summary.get("power") or {}
        run = power.get("run") or {}
        temps = [stats["max"] for key, stats in run.items() if key.startswith("temp_")]
        lines.append(
            "| {tag} | {device} | {p50} | {e2e} | {loc} | {scr} | {mis} | {pps} | {w} | {j} | {dj} | {gpu} | {t} |".format(
                tag=summary["tag"],
                device=summary["environment"].get("gpu") or summary["environment"].get("processor") or "cpu",
                p50=_fmt(latency["e2e_ms"]["p50"]),
                e2e=_fmt(p95("e2e_ms")),
                loc=_fmt(p95("locator_ms")),
                scr=_fmt(p95("scratch_ms")),
                mis=_fmt(p95("missing_ms")),
                pps=_fmt(summary["timing"]["parts_per_s"], 2),
                w=_fmt((run.get("power_w") or {}).get("mean"), 2),
                j=_fmt(power.get("energy_per_part_j"), 3),
                dj=_fmt(power.get("dynamic_energy_per_part_j"), 3),
                gpu=_fmt((run.get("gpu_util_pct") or {}).get("mean")),
                t=_fmt(max(temps) if temps else None),
            )
        )
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m gp.bench", description="GearPro 延迟 / 功耗 / 精度一致性基准")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="运行一次基准")
    run.add_argument("--images", required=True, help="图片目录（递归）")
    run.add_argument("--labels", help="标签 CSV：image,scratch,missing_hole；给出后只跑 CSV 中的图片")
    run.add_argument("--input", choices=["frame", "roi"], default="frame", help="frame=整帧走定位；roi=图片已是齿轮 ROI")
    run.add_argument("--tag", required=True, help="本次运行名称，如 nx-pt、nx-trt-fp16")
    run.add_argument("--out", help="输出目录，默认 var/bench/<tag>-<时间>")
    run.add_argument("--device", help="cuda:0 或 cpu，默认自动")
    run.add_argument("--locator", help="定位模型 .pt 或 .engine，默认 model/model1.pt")
    run.add_argument("--model2", help="Scratch V5 inference_config.json")
    run.add_argument("--missing-hole", help="Missing Hole V1 inference_config.json")
    run.add_argument("--engines", help="python -m gp.export_engine specialists 的输出目录")
    run.add_argument("--overlap", action="store_true", help="分类器 engine 与检测器并发（DLA/独立 stream）")
    run.add_argument("--share-preprocess", action="store_true", help="同一 ROI 复用 BGR→RGB 与同尺寸分类器输入")
    run.add_argument("--warmup", type=int, default=20)
    run.add_argument("--passes", type=int, default=5, help="至少遍历图片集的次数")
    run.add_argument("--min-seconds", type=float, default=60.0, help="计时阶段最短时长")
    run.add_argument("--idle-seconds", type=float, default=30.0, help="模型加载后空闲功耗采样时长")
    run.add_argument("--power", choices=["auto", "tegrastats", "nvidia-smi", "none"], default="auto")
    run.add_argument("--sample-ms", type=int, default=100)
    run.add_argument("--note", default="", help="记录功耗模式、jetson_clocks、散热等手工信息")

    compare = sub.add_parser("compare", help="精度一致性验收：candidate 相对 reference")
    compare.add_argument("reference")
    compare.add_argument("candidate")
    for key, value in DEFAULT_TOLERANCES.items():
        compare.add_argument("--" + key.replace("_", "-"), type=type(value), default=value)
    compare.add_argument("--out", help="写出 JSON 结果")

    report = sub.add_parser("report", help="多次运行汇总为 Markdown 表")
    report.add_argument("runs", nargs="+")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command == "run":
        out, summary = run_benchmark(args)
        latency = summary["latency_ms"]["e2e_ms"]
        print(f"已写入 {out}")
        print(f"e2e p50 {latency['p50']:.1f} ms / p95 {latency['p95']:.1f} ms，"
              f"{summary['timing']['parts_per_s']:.2f} parts/s")
        return 0
    if args.command == "compare":
        tolerances = {key: getattr(args, key) for key in DEFAULT_TOLERANCES}
        result = compare_runs(args.reference, args.candidate, tolerances)
        for item in result["checks"]:
            print(f"[{'PASS' if item['passed'] else 'FAIL'}] {item['check']}: {item['detail']}")
        print("精度一致性：" + ("通过" if result["passed"] else "未通过"))
        if args.out:
            Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0 if result["passed"] else 1
    print(report_table(args.runs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
