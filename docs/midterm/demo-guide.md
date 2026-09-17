# 中期答辩演示指南（约 6–8 分钟）

工作目录：`G:\CODE\Machine_vision-dual-specialist`  
分支：`integration/dual-specialist-edgemedic`

**底线：** 本次演示是 **observe-only**。屏幕上会出现 `ACTUAL EXECUTION DISABLED`。不要把提案说成「已经恢复成功」。Demo A/B/C 数字是 **FROZEN REPLAY**。

---

## 1. 演示环境

| 项 | 要求 |
|---|---|
| OS | Windows 10/11（本工作站已验证） |
| Python | 与仓库 `.venv` 一致即可；只需标准库 + 本仓库代码 |
| 可选 | 不需要摄像头、不需要 Qwen、不需要 NX SSH |
| 禁止 | 不要运行 `python -m edgemedic` 常驻环路（会尝试写 Control） |

---

## 2. 依赖检查

```bat
cd /d G:\CODE\Machine_vision-dual-specialist
git branch --show-current
git rev-parse --short HEAD
dir tools\agent_midterm_demo.py
dir edgemedic\observe.py
dir docs\midterm\scenarios
```

预期：分支为 `integration/dual-specialist-edgemedic`。

---

## 3. 启动命令（完整可复制）

```bat
cd /d G:\CODE\Machine_vision-dual-specialist
set PYTHONPATH=G:\CODE\Machine_vision-dual-specialist
python tools/agent_midterm_demo.py --scenario all --show-frozen-abc
```

单场景：

```bat
python tools/agent_midterm_demo.py --scenario A_healthy
python tools/agent_midterm_demo.py --scenario B_inspection_paused
python tools/agent_midterm_demo.py --scenario C_camera_stale
python tools/agent_midterm_demo.py --scenario D_memory --memory on
python tools/agent_midterm_demo.py --scenario D_memory --memory off
```

JSON 输出目录：`docs/midterm/runs/`（可展示给老师看 `actually_executed: false`）。

无 Web 地址（本交付为 CLI；P2 Web 未做）。

---

## 4. 建议演示顺序与讲解词

### 第一部分（45s）— 总体架构

讲解：GearPro 负责检测；Agent 读结构化 Snapshot，经 L0→L1→MEM→L2 提案；执行必须走 Control；本次演示故意断开执行。

打开技术报告 §2 架构图亦可。

### 第二部分（60s）— 正常状态

运行 A 或看 all 输出中的 `A_healthy`。

应看到：

- `fault: None`
- `proposed_action: (none)`
- `actually_executed: False`

讲解：健康状态不乱提恢复动作，避免「假阳性恢复」。

### 第三部分（60s）— CAMERA_STALE

看 `C_camera_stale`：

- `fault: CAMERA_STALE`
- `frame_age_ms=1824`
- `proposed_action: restart_camera [L1]`
- `ACTUAL EXECUTION DISABLED`

讲解：这是确定性 L1，不需要 LLM。

### 第四部分（60s）— INSPECTION_PAUSED

看 `B_inspection_paused`：

- `fault: INSPECTION_PAUSED`
- `inspection_active=False` 且相机仍 opened
- `proposed_action: resume_inspection [L1]`

讲解：与「相机坏了」不同；语义是任务暂停。历史 Demo A 在 NX replay 上验证过闭环，**今天不重放执行**。

### 第五部分（90s）— Memory ON / OFF

```bat
python tools/agent_midterm_demo.py --scenario D_memory --memory on
python tools/agent_midterm_demo.py --scenario D_memory --memory off
```

- ON：`route=MEM`，`l2.live=false`（L1 cooldown 后走经验库）
- OFF：`route=L2`，`l2.used_historical=true`，注释含 **HISTORICAL REPLAY**

讲解：同一故障，记忆命中可跳过 L2；关闭记忆则展示历史 L2 提案形状。**不是**现场 2.7s 推理。

### 第六部分（60s）— 历史恢复证据

命令已带 `--show-frozen-abc`，或单独：

```bat
python tools/agent_midterm_demo.py --show-frozen-abc --scenario A_healthy --quiet
```

指出 JSON 中 Demo A/B e2e、Demo C ON/OFF；口头强调：replay ≠ 真机；两边历史 RECOVERED ≠ 本次 RECOVERED。

### 第七部分（45s）— 成果与局限

已完成：双专项 Runtime 集成到 6.3、Control/Guardian/Verify、只读 Agent Demo、文档。  
未完成：自动恢复、真机、NX overlay 入库、调用者认证、实模型加载（本机 skip）。

---

## 5. 异常处理

| 现象 | 处理 |
|---|---|
| `ModuleNotFoundError: edgemedic` | 确认 `PYTHONPATH` 指向仓库根 |
| 场景文件缺失 | 检查 `docs/midterm/scenarios` |
| 误运行 `python -m edgemedic` | 立刻停止；中期只用 `tools/agent_midterm_demo.py` |
| 老师问「恢复了吗」 | 回答：本次只提案；历史恢复见 FROZEN REPLAY |

## 6. 退出

CLI 跑完自动退出。无需杀进程。

---

## 7. 答辩时可主动说清的四点

1. 为什么不全用大模型？——已知故障要确定性、低延迟、可测。  
2. 经验库意义？——复用已验证成功，减少 L2；不宣称提升成功率。  
3. 如何保证不危险执行？——中期结构禁止 POST；正式系统靠白名单+Verify+Guardian。  
4. 和完整 SRTP 关系？——检测与控制底座在集成；Agent 自动恢复尚未开放。
