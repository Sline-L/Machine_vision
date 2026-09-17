# P0：Qwen3-4B 双专项 Agent 技术报告

分支：`integration/dual-specialist-edgemedic`  
机制已实现；研究级有效性尚未验证。Replay ≠ 真机故障恢复。

## 1. 目标与边界

将 Qwen3-4B 接入最新双专项 GearPro：读 Snapshot → L0/L1/MEM/L2 → Authority → Control → Verify。  
默认 `observe_only`；仅隔离 Replay + `--execution-mode execute_replay` 允许白名单低风险执行。  
9B / 真机自动恢复 / fresh holdout：**未做**。

## 2. 架构（对应当前代码）

```
GearPro (Scratch V5 + Missing Hole)  --HTTP-->  EdgeMedic
  /api/state  SystemSnapshot / control-view
  /api/action whitelist + Verify

EdgeMedic tick (edgemedic/runtime.run_once):
  adapter.adapt_snapshot
  → classify_fault / decide (L0/L1)
  → EpisodeStore.suggest (MEM)
  → reasoner.complete_report (L2 / Qwen3-4B)
  → authority.decide_execution
  → client.post_action  (仅 execute_replay)
  → Verify + optional episode record
```

## 3. 关键模块

| 模块 | 路径 | 职责 |
|---|---|---|
| Adapter | `edgemedic/adapter.py` | v1/v2 specialists 提升，不破坏对外 schema |
| Policy | `edgemedic/policy.py` | L0/L1 确定性规则 |
| Memory | `edgemedic/memory.py` | ≥3 次 verified 成功才 suggest |
| Reasoner | `edgemedic/reasoner.py` | llama-server + GBNF |
| Authority | `edgemedic/authority.py` | L2 高风险 DRY_RUN；低风险才可执行 |
| Client | `edgemedic/client.py` | Control HTTP |
| Runtime | `edgemedic/runtime.py` | 单 tick 闭环 |
| Read-only | `edgemedic/readonly_client.py` | 结构禁止 POST |
| Demo | `tools/agent_p0_4b.py` | Demo A–F |

## 4. 何时调用 4B

仅当存在 named fault，且 L1/MEM 未给出提案（或先验失败）时。  
合成场景 `L2_unknown_scratch`：`UNKNOWN_SCRATCH_V5` 无 L1 动词 → 强制进入 L2，**未改正式分类规则**。

## 5. NX 实测摘要（2026-09-17）

| 项 | 结果 |
|---|---|
| Qwen3-4B | `127.0.0.1:8080`，模型 `qwen3-4b` |
| 双专项实例 | `/home/jetson/Projects/p0-gearpro-dual` Control `:8788`（未覆盖 edgemedic-live / 原 8787） |
| Scratch V5 | `loaded=True`，infer_ok |
| Missing Hole | `loaded=True`，infer_ok |
| Demo C（4B） | `l2_invoked=True`，`protocol_status=valid_structured`，提案 `restart_camera`，`executed=False`（observe-only），L2≈2.05–2.66s |
| Demo E（Replay） | `INSPECTION_PAUSED`→L1 `resume_inspection`→`verify=mission`→`RECOVERED`，`executed=True` |
| 4B 执行闭环 | **未完成**（不把 C+E 拼接成一条 4B 恢复链） |

Overlay 参考 SHA256（归档于 `_overlay_ref/`，未覆盖）：见 evidence-index。

## 6. 修复

`gp/verify.py` `assess_resume`：禁止 `del params` 后再使用（否则 resume 抛 `params referenced before assignment`）。  
`gp/runtime.py`：恢复 `ReplayCapture` 接线（双专项集成曾丢失）。

## 7. 局限与后续

- 生产自动恢复：**未授权、未上线**。  
- 当前 8787 仍为旧 Scratch-only 实例；验收用独立 8788。  
- 9B：仅接口预留（同一 reasoner/Control 协议），P0 后另开。  
- 性能：单次测量，非均值。
