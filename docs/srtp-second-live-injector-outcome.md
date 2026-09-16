# Second NX live injector — outcome

```text
research injector only
requires GEARPRO_RESEARCH_INJECT=1
does not mutate health state
not enabled by default
```

```text
AGENT ARCHITECTURE:
SUFFICIENT FOR CURRENT RESEARCH STAGE
NX END-TO-END RECOVERY:
VERIFIED FOR 2 DISTINCT RUNTIME FAULT FAMILIES
  1. INSPECTION_PAUSED
  2. CAMERA_STALE
MULTI-FAULT MECHANISM:
SUPPORTED BY ADDITIONAL SYNTHETIC / IN-PROCESS EVIDENCE
MULTI-FAULT LIVE GENERALITY:
PARTIALLY VALIDATED
PHYSICAL DEVICE FAULT RECOVERY:
NOT VALIDATED
```

## Claim (use this wording)

在 Jetson NX 实际运行环境中，系统已对 `INSPECTION_PAUSED` 与 replay capture pipeline 的 `CAMERA_STALE` 两类独立运行时故障完成端到端恢复验证。进一步的物理摄像头、串口等硬件故障验证受实验平台和安全注入条件限制。

Do not write an unqualified “真实运行故障” that a reader could take as `/dev/video*` unplug or driver kill. This NX board has no `/dev/video*`. Capture freeze stalls the replay publish loop; telemetry `frame_age_ms` grows through the normal path.

## Injector

Env-gated: `GEARPRO_RESEARCH_INJECT=1` and freeze file `/tmp/gearpro-freeze-camera` (override `GEARPRO_INJECT_FREEZE_CAMERA`). If the env is not `1`/`true`/`yes`/`on`, the freeze file has **no** effect.

`restart_camera` may run for `source=camera` (unchanged production authority) and `source=replay` (research freeze recovery). `source=video` stays blocked.

No health-field writes. No new recovery verb. No third live family.

## NX live result

GearPro with `GEARPRO_RESEARCH_INJECT=1`, overlay `edgemedic-live`, `tools/nx_live_camera_stale.py`.

| Gate | Result |
| --- | --- |
| safe | freeze file only |
| repeatable | touch freeze → wait → L1 |
| detected by normal inspection | `CAMERA_STALE` at `frame_age_ms≈1115`, `opened=true`, `inspection_active=true` |
| creates real incident | EdgeMedic incident `CAMERA_STALE` |
| existing whitelist action | L1 `restart_camera` |
| objective verify | `verify_level=mission`, `recovery_outcome=RECOVERED`, `control_accepted=true` |

Artifact: `/home/jetson/Projects/edgemedic-live/results/second_live_family/summary.json`
