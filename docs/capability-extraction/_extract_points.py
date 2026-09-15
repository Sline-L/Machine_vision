"""One-shot extraction of classifier-only validation operating points."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FINAL = ROOT / "final"


def op20(row: dict) -> dict:
    ops = row.get("operating_points") or {}
    return ops.get("0.2") or ops.get("0.20") or {}


def main() -> None:
    lb = json.loads((FINAL / "leaderboard.json").read_text(encoding="utf-8"))
    rows = []
    for row in lb:
        kind = str(row.get("kind") or row.get("type") or "")
        name = str(row.get("name") or "")
        # classifier-only: single classifier or fusion without detector
        is_cls = kind in {"classifier", "fusion"} or "classifier" in name.lower()
        point = op20(row)
        if not point:
            continue
        # Prefer explicit classifier / classifier_mean / classifier_max names
        fusion_hint = ""
        rule = row.get("rule") or row.get("fusion") or {}
        if isinstance(rule, dict):
            fusion_hint = str(rule.get("type") or "")
        rows.append(
            {
                "name": name,
                "kind": kind,
                "stage": row.get("stage"),
                "family": row.get("family"),
                "fusion": fusion_hint,
                "threshold": point.get("threshold"),
                "recall": point.get("recall"),
                "precision": point.get("precision"),
                "fpr": point.get("fpr"),
                "f1": point.get("f1"),
                "meets_val_target": (
                    float(point.get("recall") or 0) >= 0.95
                    and float(point.get("fpr") or 1) <= 0.20
                ),
            }
        )

    # Also dump every leaderboard row summary for audit
    out_dir = Path(__file__).resolve().parent
    summary = sorted(rows, key=lambda r: (-float(r["recall"] or 0), float(r["fpr"] or 1)))
    (out_dir / "leaderboard_val_points.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    # Focus set: single classifiers + names that look like classifier-only fusions
    focus = [
        r
        for r in summary
        if r["kind"] == "classifier"
        or str(r["name"]).startswith("classifier_")
        or "classifier_mean" in str(r["name"])
        or "classifier_max" in str(r["name"])
        or (r["fusion"].startswith("classifier") if r["fusion"] else False)
    ]
    (out_dir / "classifier_only_val_candidates.json").write_text(
        json.dumps(focus, indent=2), encoding="utf-8"
    )

    with (out_dir / "classifier_only_val_candidates.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(focus[0].keys()) if focus else [])
        if focus:
            writer.writeheader()
            writer.writerows(focus)

    print(f"leaderboard rows: {len(lb)}")
    print(f"summarized: {len(summary)}")
    print(f"classifier-only focus: {len(focus)}")
    for r in focus:
        flag = "PASS_VAL" if r["meets_val_target"] else "miss"
        print(
            f"{flag:8} {r['kind']:12} {r['name']}: "
            f"R={r['recall']:.4f} FPR={r['fpr']:.4f} thr={r['threshold']} F1={r['f1']}"
        )


if __name__ == "__main__":
    main()
