# SRTP RQ2 — cross-fault live memory evidence

```text
controlled routing experiment
not natural runtime routing
effectiveness_claimed = false
third live family = not pursued
V3-1 = untouched
structured/raw protocol = untouched
authority = unchanged
```

```text
INSPECTION_PAUSED live memory evidence
CAMERA_STALE live memory evidence (replay capture pipeline)
```

在 Jetson NX 实际运行环境中，系统已对 `INSPECTION_PAUSED` 与 replay capture pipeline 的 `CAMERA_STALE` 两类独立运行时故障完成端到端恢复验证。进一步的物理摄像头、串口等硬件故障验证受实验平台和安全注入条件限制。

Artifact: `/home/jetson/Projects/edgemedic-live/results/rq2_camera_stale_memory/summary.json`  
Pause/resume pair remains `results/research_evidence_v2/summary.json`.

---

## What this is

Phase A accumulated **three** NX live `CAMERA_STALE` recoveries through freeze → normal inspection → L1 `restart_camera` → mission verify. Episodes were **not** hand-written. After that, `suggest("CAMERA_STALE") = restart_camera`.

Phase B is a **controlled routing** pair on the same freeze signature with **L1 disabled**, so memory vs L2 is visible. It is not the natural L0→L1→MEM→L2 order.

## CAMERA_STALE Phase B (n=1 pair)

| | memory ON | memory OFF |
| --- | --- | --- |
| route chosen | **MEM** | **L2** |
| memory hit | `restart_camera` | none |
| L2 invoked | **false** | **true** (`l2_latency_ms=2424`) |
| L2 proposal | — | `restart_camera` |
| Control | accepted | accepted |
| verified recovery | **RECOVERED** (mission) | **RECOVERED** (mission) |
| e2e latency | 2235 ms | 4626 ms |

Mechanism sentence (not a success-rate claim):

> Verified experience retrieval can bypass expensive small-model reasoning for previously solved fault patterns.

On this pair both arms recovered. Memory did **not** uniquely create success; L2 also proposed the whitelist action. The observable difference is **skipping ~2.4 s of Qwen** on a known signature. Do not upgrade this to “significantly higher recovery rate.”

## Cross-fault RQ2 (with INSPECTION_PAUSED v2)

| | INSPECTION_PAUSED (v2) | CAMERA_STALE (this run) |
| --- | --- | --- |
| live NX path | pause via Control | replay capture freeze (env-gated) |
| ≥3 verified successes | yes (`resume_inspection`) | yes (`restart_camera`) |
| memory ON (L1 off) | MEM `resume_inspection`, L2 skipped, RECOVERED | MEM `restart_camera`, L2 skipped, RECOVERED |
| memory OFF (L1 off) | L2 ~2.12 s, proposed **pause** (wrong), Control **rejected**, FAILED | L2 ~2.42 s, proposed **restart_camera**, Control accepted, RECOVERED |

Two different live signatures, same retrieval gate (`>=3` verified successes), same skip-L2 pattern when memory is primed. The off-arm outcome differs by fault: pause memory-off failed at Control; camera memory-off still recovered because L2 guessed the existing verb.

Physical `/dev/video*` and serial hardware faults remain **not validated**. No third live family.

## Isolation

No V3 retune, no structured/raw protocol edit, no new recovery verb, no authority expansion.
