from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCORE_COLUMNS = [
    "run_id",
    "cfg",
    "model",
    "build_id",
    "timing_cache",
    "subset",
    "stem",
    "label",
    "logit_raw",
    "det_max_conf",
    "det_n_cand",
    "engine_sha256",
    "tensor_sha256",
    "device",
    "ts",
]


def make_run_id(cfg: str, model: str, build_id: str = "na") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{stamp}_{cfg}_{model}_{build_id}"


def append_scores(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.is_file()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SCORE_COLUMNS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        for row in rows:
            out = {key: "" if row.get(key) is None else row[key] for key in SCORE_COLUMNS}
            for key in ("logit_raw", "det_max_conf"):
                if out[key] != "" and out[key] is not None:
                    out[key] = repr(float(out[key]))
            writer.writerow(out)
