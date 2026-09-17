# P0 4B 证据索引

## Git（本地，未 push）

| 项 | 值 |
|---|---|
| 分支 | `integration/dual-specialist-edgemedic` |
| 基线（冲刺前） | `9472832` |
| 仓库 | `G:\CODE\Machine_vision-dual-specialist` |

## NX 部署（未覆盖 overlay）

| 路径 | 用途 |
|---|---|
| `/home/jetson/Projects/p0-4b-agent` | P0 Agent |
| `/home/jetson/Projects/p0-gearpro-dual` | 双专项 GearPro 隔离实例（`:8001`/`:8788`） |
| `/home/jetson/Projects/edgemedic-live` | 原始 overlay（只读参考） |
| `/home/jetson/Projects/Machine_vision` pid 14179 | 原 Control `:8787`（保留） |

### Overlay 参考 SHA256（`_overlay_ref/`）

```
0CE97FBC79B6E53E0DD51FB022A4AB15C2536C96AA1BEC27F2B9F40E2FAD761E  authority.py
D65737C88AC52EC329A3197D1886E91BA89181F4017008FEE77AE71E5F1CAFC1  client.py
2CC14221F985991BAAC13885C1B5DAE9D736572FD297014FA0523F2DA901C1CF  reasoner.py
AC6D4E7F7FC3B81E1B78B10EBA4CBAA17C5C41ECD6B3C9FC54584200A6F17E4F  runtime.py
```

## 测试

```bat
set PYTHONPATH=G:\CODE\Machine_vision-dual-specialist
python -m unittest tests.test_agent_p0_4b tests.test_agent_midterm_demo -v
```

NX：`python3 -m unittest tests.test_agent_p0_4b -v` → 8 OK。

## 运行产物（NX，部分已拷贝）

- `docs/midterm/runs/p0/demo_A.json` — 双专项 loaded
- `docs/midterm/runs/p0/demo_C.json` — 真实 4B
- `docs/midterm/runs/p0/demo_E.json` — Replay L1 RECOVERED

## 4B 调用证据（Demo C）

- model: `qwen3-4b`
- endpoint: `http://127.0.0.1:8080`
- decode: grammar / `valid_structured`
- latency_ms ≈ 2050–2660
- proposed: `restart_camera`
- `actually_executed`: false（observe-only）
- why L2: `UNKNOWN_SCRATCH_V5` 无 L1 动词

## 恢复证据（Demo E，双专项 `:8788`）

- induced `pause_inspection` → mission
- Agent L1 `resume_inspection` → `executed=true`，`verify_level=mission`，`RECOVERED`
- 路由：**L1**，不是 4B

## 历史研究证据

勿与本次集成混淆：`docs/midterm/frozen/`、edgemedic-live final_demo。
