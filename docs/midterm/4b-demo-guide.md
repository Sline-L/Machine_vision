# 4B Agent 演示指南（可复现）

隔离环境：NX `p0-gearpro-dual`（Web `:8001` / Control `:8788`）+ `p0-4b-agent` + llama-server `:8080`。
**禁止**对生产 `:8787` 使用 `execute_replay`。

## 1. 启动隔离双专项

```bash
cd /home/jetson/Projects/p0-gearpro-dual
nohup env GEARPRO_REPLAY_DIR=/home/jetson/Projects/p0-gearpro-dual/tests/replay/frames \
  EDGEMEDIC_STATUS_URL=http://127.0.0.1:8790 \
  .venv/bin/python3 -m gp --host 127.0.0.1 --port 8001 --control-port 8788 \
  >/tmp/p0-gearpro-dual.log 2>&1 &
# warmup ~15s 后检查双专项 infer_ok
curl -s http://127.0.0.1:8788/api/state | python3 -c \
  'import sys,json;d=json.load(sys.stdin);s=d["specialists"];print(s["scratch_v5"]["infer_ok"],s["missing_hole_v1"]["infer_ok"])'
```

## 2. 启动 Agent（隔离可 execute_replay；默认仍不 arm）

```bash
cd /home/jetson/Projects/p0-4b-agent
export PYTHONPATH=$PWD
# 演示恢复：execute_replay；生产应改为 observe_only
nohup python3 -m edgemedic.service \
  --control-url http://127.0.0.1:8788 \
  --llm-url http://127.0.0.1:8080 \
  --status-port 8790 \
  --execution-mode execute_replay \
  --pidfile /tmp/edgemedic-agent.pid \
  --auto-monitor >/tmp/edgemedic-agent.log 2>&1 &
curl -s http://127.0.0.1:8790/status | python3 -m json.tool | head -25
# 期望：llm_ready=true，recovery_armed=false
```

一键脚本：`deploy/start-edgemedic-agent.sh`（读取 `deploy/edgemedic-agent.env`）。

## 3. GUI 操作（实时 Agent，非历史 JSON）

1. 打开 `http://127.0.0.1:8001/`，登录，取得操作权。
2. 侧栏 **EDGEMEDIC AGENT**：应显示服务在线、4B 就绪。
3. **开始检测** → 「监测中」；「恢复武装=否」。
4. 点 **启用恢复授权**（仅 `execute_replay` 可点；observe_only 会失败）。
5. （可选）用 Control 诱导 pause，或等待真实故障；面板应出现路由/提案/Verify/Control 记录。
6. **停止检测** → 监测关闭，恢复授权撤销。

HTTP 等价验收：

```bash
python3 tools/nx_p0_gui_ops_chain.py \
  --web-url http://127.0.0.1:8001 \
  --control-url http://127.0.0.1:8788 \
  --json-out docs/midterm/runs/p0/gui_ops_chain.json
```

浏览器人工验收若未做，报告中保持 `browser_manual_qa=NOT_RUN`。

## 4. 强制 4B 闭环（disable_l1）

```bash
python3 tools/nx_p0_4b_closed_loop.py \
  --control-url http://127.0.0.1:8788 \
  --llm-url http://127.0.0.1:8080 \
  --execution-mode execute_replay \
  --json-out docs/midterm/runs/p0/4b_closed_loop_live.json
```

## 5. 自然路由

```bash
# A=L1，B=自然 L2+4B（observe）
python3 tools/nx_p0_natural_routing.py \
  --control-url http://127.0.0.1:8788 \
  --llm-url http://127.0.0.1:8080 \
  --execution-mode observe_only \
  --json-out-dir docs/midterm/runs/p0
```

## 6. systemd（需操作员批准后执行）

模板已校验，**默认未安装**：

```bash
# 审查
cat /home/jetson/Projects/p0-4b-agent/deploy/edgemedic-agent.service
cp deploy/edgemedic-agent.env.example deploy/edgemedic-agent.env
# 编辑：EDGEMEDIC_EXECUTION_MODE=observe_only（生产）或 execute_replay（仅隔离 :8788）

# 安装（需 sudo；会注册用户服务单元，勿在未确认时指向 :8787）
sudo cp deploy/edgemedic-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now edgemedic-agent.service   # 仅批准后
sudo systemctl status edgemedic-agent.service
sudo systemctl stop edgemedic-agent.service
sudo systemctl disable edgemedic-agent.service
# 回滚
sudo rm /etc/systemd/system/edgemedic-agent.service
sudo systemctl daemon-reload
```

用户级临时验证（不写 `/etc`）：

```bash
systemd-run --user --unit=edgemedic-agent-smoke --collect \
  -p WorkingDirectory=/home/jetson/Projects/p0-4b-agent \
  -E PYTHONPATH=/home/jetson/Projects/p0-4b-agent \
  /usr/bin/python3 -c 'print("ok")'
```

## 7. 停止隔离实例

```bash
curl -s -X POST http://127.0.0.1:8790/shutdown || kill $(cat /tmp/edgemedic-agent.pid)
kill $(cat /tmp/p0-gearpro-dual.pid)
# 勿杀 :8787/:8000/llama-server（除非另行批准）
```
