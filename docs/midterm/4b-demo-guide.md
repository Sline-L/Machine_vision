# P0 4B 演示指南

## 环境

- Windows 工作树：`G:\CODE\Machine_vision-dual-specialist`
- NX Agent：`/home/jetson/Projects/p0-4b-agent`
- NX 双专项 GearPro（隔离）：`/home/jetson/Projects/p0-gearpro-dual` → Web `8001` Control `8788`
- Qwen：`127.0.0.1:8080`（已有 llama-server，勿擅自重启）
- 原产线 Control `8787`：**不要停**

## 启动（NX）

```bash
# 双专项 Replay（若未在跑）
cd /home/jetson/Projects/p0-gearpro-dual
nohup env GEARPRO_REPLAY_DIR=/home/jetson/Projects/p0-gearpro-dual/tests/replay/frames \
  .venv/bin/python3 -m gp --host 127.0.0.1 --port 8001 --control-port 8788 \
  >/tmp/p0-gearpro-dual.log 2>&1 &

# 确认模型已加载
curl -s http://127.0.0.1:8788/api/state | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['specialists']['scratch_v5']['loaded'],d['specialists']['missing_hole_v1']['loaded'])"
# 若 inspection 未开：POST resume_inspection（需 request_id）

cd /home/jetson/Projects/p0-4b-agent
export PYTHONPATH=/home/jetson/Projects/p0-4b-agent
```

## 演示命令

```bash
# A 真实双专项状态
python3 tools/agent_p0_4b.py --demo A --control-url http://127.0.0.1:8788

# B 诊断（无 LLM）
python3 tools/agent_p0_4b.py --demo B --control-url http://127.0.0.1:8788

# C 真实 4B（合成 UNKNOWN_SCRATCH，observe-only）
python3 tools/agent_p0_4b.py --demo C --control-url http://127.0.0.1:8788 --llm-url http://127.0.0.1:8080

# D Authority（含高风险 DRY_RUN 示例）
python3 tools/agent_p0_4b.py --demo D --control-url http://127.0.0.1:8788 --llm-url http://127.0.0.1:8080

# E 隔离 Replay L1 恢复（显式开放执行）
python3 tools/agent_p0_4b.py --demo E --control-url http://127.0.0.1:8788 --execution-mode execute_replay

# F 恢复后专项视图
python3 tools/agent_p0_4b.py --demo F --control-url http://127.0.0.1:8788 --execution-mode execute_replay
```

默认 `observe_only`：屏幕出现 `ACTUAL EXECUTION DISABLED`。

## 预期

| Demo | 预期 |
|---|---|
| A | scratch/missing `loaded=true` |
| C | `l2_invoked=true`，结构化提案，`executed=false` |
| E | `route=L1`，`executed=true`，`verify=mission`，`RECOVERED` |

## 讲解要点

1. 4B 只提案，Authority/Control 才执行。  
2. C 证明 4B；E 证明 L1 恢复——不要拼成“4B 恢复成功”。  
3. Replay ≠ 物理摄像头故障。

## 退出

CLI 自动退出。停双专项：`kill $(cat /tmp/p0-gearpro-dual.pid)`（勿杀 8787）。
