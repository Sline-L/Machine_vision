# Guardian 与 Reflex v1

L0/L1 **确定性**。L2（Qwen）只在 L1/记忆失败后读 Snapshot 出 `{tool, params}`。EdgeMedic 与 GearPro **分进程**：本包只访问 Control API，不 import `gp`。

两层 Guardian 职责不同，不是重复：

| 名称 | 位置 | 职责 |
| --- | --- | --- |
| **Hard Guardian** | GearPro 进程内 `gp/guardian.py` | 不可违反的 invariant。即使 EdgeMedic / Qwen / Web 全死也有效。**只能降能力，不能自己升能力**（例如 FULL→SAFE_STOP，不能 SAFE_STOP→FULL）。 |
| **Autonomy Guardian** | Control API accept/timeout/retry/verify/rollback | 判断这条动作是否允许、次数、precondition、能否回滚。人与 Agent 共用。 |

80°C 是 **operational policy threshold**，不是 Jetson 硬件绝对极限。

```text
python gp_main.py
python -m edgemedic --url http://127.0.0.1:8787
```

## L0 Guardian

| 规则 | 条件 | 动作 |
| --- | --- | --- |
| `THERMAL_STOP` | `temperature_c >= 80`（策略阈值）且当前不是 `SAFE_STOP` | `set_inference_profile SAFE_STOP` |

Hard Guardian 与 EdgeMedic L0 共用同一条温度策略。Level 3（reboot/shell）v1 不存在。

## L1 Reflex（不问 LLM）

同一拍最多一条动作。规则冷却 10 秒。`SAFE_STOP` 之后 Reflex 不再自动恢复。

| 规则 | 条件 | 动作 |
| --- | --- | --- |
| `CAMERA_STALE` | 未打开（且不是“视频检测中”），或 `frame_age_ms > 1000`，或 `frame_seq` 2 秒不增加 | `restart_camera` |
| `WORKER_FAIL` | `scratch_v5.error_count` 相对上次观察增加 | `restart_worker` |
| `SERIAL_FAIL` | `consecutive_failures >= 1`，或未连接且 `health < 1` | `reconnect_serial` |
| `V5_OVERLOAD` | 当前 `FULL`，V5 ≥200 ms | `set_inference_profile SPARSE` |
| `LOCATOR_OVERLOAD` | 当前 `FULL`，locator ≥120 ms 且 V5 未过载 | **不定性切 TRT**（留给 L2/记忆；等真实 workload 再决定是否 Promote） |

未知故障不发明 L1 规则。Repair Memory **只学习 `function` / `mission` 级 Verify**；`config` 级不算恢复成功，也不写入成功/失败计数。至少 3 次 function 成功且成功多于失败，才允许记忆层 suggest。不要把记忆自动编译进 Python Reflex；SRTP 阶段最多做到 Policy Candidate。

## Verify 三级

| 级别 | 含义 | rollback | Repair Memory |
| --- | --- | --- | --- |
| `none` | 动作没粘住 | 是 | 记失败 |
| `config` | 配置/档位/backend 已切换 | 否 | **不学习** |
| `function` | 一次真实 infer 或 IO 恢复成功 | 否 | 可学习 |
| `mission` | 短窗口内 utility/延迟可接受 | 否 | 可学习 |

响应里 `verified` / `recovery_success` 仅在 function 或 mission 为 true。`config_verified` 表示不要 rollback。

## L2 Qwen

仅当 L0/L1 没有动作，或动作连 `config` 都没过，且当前确有故障签名时，才请求板上 `llama-server`。健康快照不打 Qwen。目标是：**在白名单内对规则盖不住的状态组合做安全决策，证据不足则 abstain（`tool: null`）**。工具名纠错只允许 1–2 字符、且唯一更近的 lexical 修正。

## 与 Control API

L0/L1/记忆用 `source=reflex`，L2 用 `source=reasoner`。Web 仪表盘与 Agent 共用 `ControlService`：浏览器仍走 FastAPI `/api/v1/*`，但 start/stop/settings/camera/video/reset 内部调用 `runtime.human_action` → 同一套 accept/verify/rollback。`apply_settings` / `use_camera` / `use_video` / `reset_stats` 仅 `source=human`。成功写入 `var/settings.json` 时同步 `var/settings.last_known_good.json`。Episode 记忆记录 Memory Harm Rate：`harms/suggests`，错误历史回放或不 stick（`verify_level=none`）计为 harm。

Mission 级 Verify 看 **inspection 窗口**（最少 N 次周期、output_valid 比例、**p95** 延迟、camera health、utility、无新的 critical incident），不是固定 sleep。SAFE_STOP / pause / 串口恢复在 function 成立时记为 mission。论文指标应分开统计 `ASR_func` 与 `ASR_mission`。

合成评测：`python -m edgemedic.bench --reasoner mock`；接板上 Qwen：`--reasoner qwen`。实验导出：`python -m edgemedic.experiment`。UAL（unsafe 提议被实际执行的比例）必须为 0。
