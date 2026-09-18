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

## 9. NX 实测记录（2026-09-17，SSH `jetson-nx` / 192.168.55.2）

主机：`yahboom`，用户 `jetson`。

| 检查 | 结果 |
|---|---|
| 中期 Demo 同步目录 | `/home/jetson/Projects/midterm-agent-demo` |
| `unittest tests.test_agent_midterm_demo` | **10 OK**（含 live_l2 提案标记） |
| `python3 tools/agent_midterm_demo.py --scenario all` | A/B/C/D 路由正确；全部 `executed=False`；五面板输出 |
| Qwen `127.0.0.1:8080` | HTTP 200，模型 `qwen3-4b` |
| GearPro Control `127.0.0.1:8787` | **已起**（replay + Control）；仅做 GET /api/state，**未** POST /api/action |
| `E_live` | 健康 replay：`fault=None`，`executed=False`，`input_source=LIVE GET /api/state`；五面板可见 |
| `--live-l2` on healthy | **正确跳过** L2（无 L2-needed fault）；meta 记录 skip 原因 |
| Live L2 wiring probe | 合成 `C_camera_stale` + L1 cooldown + overlay reasoner → `route=L2`，`propose=restart_camera`，`l2_live=True`，`executed=False`，latency≈2.5s，`protocol_status=valid_structured`。产物：`docs/midterm/runs/E_live_l2_wiring_probe.json`（NX）。**不是** Demo C OFF 历史数字复现 |
| 冻结 `results/final_demo/demo_{a,b,c}.json` | SHA256 见下；e2e 与答辩引用 **一致** |
| Live `reasoner.complete`（合成探针） | 服务可达；合成 CAMERA_STALE 曾返回 `None`（`reasoning_content` 非空、`content` 空）。**不能**记成 Demo C OFF 复现 |

### 冻结文件 SHA256（NX 路径）

```
dcfa9bf49679bd37eec690befcec8c1929a0188970955a5726ebda08640eace8  .../final_demo/demo_a.json
bf40e7daaec862449c0c78205484761dd9e47d66c104290b2f5eb0c29fb82b84  .../final_demo/demo_b.json
f7367f41bb7fa878d2c151628df468347cc7a00b7a022ba0f21d1f82c11b3754  .../final_demo/demo_c.json
```

### 冻结数值核对

| 项 | 文件内 | 答辩引用 | 匹配 |
|---|---|---|---|
| Demo A e2e | 2152.7 → 2153 | 2153 | Yes |
| Demo B e2e | 2136.3 → 2136 | 2136 | Yes |
| Demo C ON | route=MEM, e2e=2240.9, l2=false | 2241 / MEM | Yes |
| Demo C OFF | route=L2, e2e=4928.5, l2_ms=2704 | 4929 / 2704 | Yes |

未重跑 `tools/nx_final_demo.py`（会 `post_action` 改 Runtime）。
