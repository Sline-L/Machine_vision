# Guardian 与 Reflex v1

L0 Guardian 与 L1 Reflex **确定性**。L2（Qwen）只在 L1/记忆失败后读 Snapshot 出 `{tool, params}`。EdgeMedic 与 GearPro **分进程**：本包只访问 Control API，不 import `gp`。

```text
python gp_main.py
python -m edgemedic --url http://127.0.0.1:8787
```

## L0 Guardian

| 规则 | 条件 | 动作 |
| --- | --- | --- |
| `THERMAL_STOP` | `temperature_c >= 80` 且当前不是 `SAFE_STOP` | `set_inference_profile SAFE_STOP` |

GearPro 进程内还有同一条温度兜底（`gp/guardian.py`），即使 EdgeMedic 没启动也会停检测。Level 3（reboot/shell）v1 不存在，Control API 不会接受。

## L1 Reflex（不问 LLM）

同一拍最多一条动作。规则冷却 10 秒。`SAFE_STOP` 之后 Reflex 不再自动恢复。

| 规则 | 条件 | 动作 |
| --- | --- | --- |
| `CAMERA_STALE` | 未打开（且不是“视频检测中”），或 `frame_age_ms > 1000`，或 `frame_seq` 2 秒不增加 | `restart_camera` |
| `WORKER_FAIL` | `scratch_v5.error_count` 相对上次观察增加 | `restart_worker` |
| `SERIAL_FAIL` | `consecutive_failures >= 1`，或未连接且 `health < 1` | `reconnect_serial` |
| `OVERLOAD_SPARSE` | 当前 `FULL`，且 locator ≥120 ms 或 V5 ≥200 ms | `set_inference_profile SPARSE` |

未知故障不发明 L1 规则。病例写入 episode memory；**一次成功不会变成规则**，至少 3 次 verify 成功且成功多于失败，才允许记忆层复用同一动作。不要把记忆自动编译进 Python Reflex。

## L2 Qwen

仅当 L0/L1 没有动作，或 L1/记忆动作 `verified=false`，且当前确有故障签名时，才请求板上 `llama-server`（默认 `http://127.0.0.1:8080`）。L2 只看 SystemSnapshot，只准输出 `{"tool","params"}`，再走同一 Control API，`source=reasoner`。`--no-llm` 可关掉。

健康快照不打 Qwen。L2 冷却 30 秒。

## 与 Control API

L0/L1/记忆用 `source=reflex`，L2 用 `source=reasoner`。一律白名单、precondition、timeout、verify、rollback。`verified=false` 不得当成修复成功，也不得计入 episode 成功次数。
