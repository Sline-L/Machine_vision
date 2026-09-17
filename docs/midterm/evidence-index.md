# 中期成果证据索引

生成环境：Windows 工作站 `G:\CODE\Machine_vision-dual-specialist`  
NX `/home/jetson/Projects/edgemedic-live`：**不可达**（未能现场重算 SHA）。

---

## 1. Git

| 项 | 值 |
|---|---|
| 分支 | `integration/dual-specialist-edgemedic` |
| Step 6.3 HEAD（冲刺前） | `85c7c714d4bf18c66ef127c297f37c68ab304ca5` |
| 冲刺提交 | 见交付报告中的最新 HEAD |

---

## 2. 核心源码（本次 / 集成）

| 类别 | 路径 |
|---|---|
| 只读诊断 | `edgemedic/observe.py` |
| 只读客户端 | `edgemedic/readonly_client.py` |
| L0/L1 | `edgemedic/policy.py` |
| EpisodeStore | `edgemedic/memory.py` |
| Demo CLI | `tools/agent_midterm_demo.py` |
| Control/Verify/Guardian | `gp/control.py`, `gp/verify.py`, `gp/guardian.py`, `gp/runtime.py` |
| 中期测试 | `tests/test_agent_midterm_demo.py` |

---

## 3. 演示输入（SYNTHETIC）

- `docs/midterm/scenarios/A_healthy.json`
- `docs/midterm/scenarios/B_inspection_paused.json`
- `docs/midterm/scenarios/C_camera_stale.json`

标记：`input_source: SYNTHETIC`。

---

## 4. 冻结 / 历史材料（FROZEN REPLAY）

| 文件 | 含义 |
|---|---|
| `docs/midterm/frozen/episodes_camera_stale.json` | MEM 演示用 episode 计数（非 NX 原库） |
| `docs/midterm/frozen/l2_camera_stale_historical.json` | 历史 L2 提案形状 |
| `docs/midterm/frozen/demo_abc_historical.json` | Demo A/B/C 引用数字 |

**不是** live inference；**不是** 新恢复实验。

---

## 5. 本次演示产物

- `docs/midterm/runs/*.json` — `agent_midterm_demo.py` 写出的诊断报告  
- 特征：`actually_executed: false`，`recovery_claimed: false`

---

## 6. 测试记录

本地命令：

```bat
set PYTHONPATH=G:\CODE\Machine_vision-dual-specialist
python -m unittest tests.test_agent_midterm_demo -v
python -m unittest discover -s tests -q
python tools/agent_midterm_demo.py --scenario all --show-frozen-abc
```

Step 6.3 基线：90 tests OK，skipped=2（无 torch）。  
冲刺后全量：`unittest discover` → **99 tests OK，skipped=2**（含 `tests.test_agent_midterm_demo`）。

---

## 7. 文档交付

| 文档 | 路径 |
|---|---|
| 技术报告 | `docs/midterm/agent-technical-report.md` |
| 演示指南 | `docs/midterm/demo-guide.md` |
| 技术问答 | `docs/midterm/technical-qa.md` |
| 本索引 | `docs/midterm/evidence-index.md` |
| Step 6.3 | `docs/integration/step-6.3-verify.md` |

---

## 8. 明确不在证据包中的内容

- 模型权重 / 数据集  
- NX overlay 二进制与原始日志（本机不可访问）  
- fresh holdout 任何结果  
- 「本次 live L2」日志（未调用）
