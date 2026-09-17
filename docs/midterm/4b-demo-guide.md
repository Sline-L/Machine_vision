# 4B Agent 演示指南（可复现）

隔离环境：NX `p0-gearpro-dual`（Web `:8001` / Control `:8788`）+ `p0-4b-agent` + llama-server `:8080`。
**禁止**对生产 `:8787` 使用 `execute_replay`。

本机隧道示例（Windows → NX）：

```text
ssh -L 18001:127.0.0.1:8001 -L 18790:127.0.0.1:8790 jetson@192.168.55.2
浏览器打开 http://127.0.0.1:18001/
```

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
export EDGEMEDIC_EXECUTION_MODE=execute_replay
export EDGEMEDIC_CONTROL_URL=http://127.0.0.1:8788
bash deploy/start-edgemedic-agent.sh
curl -s http://127.0.0.1:8790/status | python3 -m json.tool | head -25
# 期望：llm_ready=true，recovery_armed=false
```

脚本默认 `observe_only`；对 `:8787` 的 `execute_replay` 会直接拒绝（exit 2）。

## 3. GUI 浏览器操作（必做；勿用 HTTP 冒充）

1. 打开 `http://127.0.0.1:8001/`（或隧道 `18001`），登录，取得操作权。
2. 侧栏 **EDGEMEDIC AGENT**：服务在线、4B 就绪、执行模式可见。
3. **开始检测** → 「监测中」；「恢复武装=否」。
4. 点 **启用恢复授权**（仅 `execute_replay` 可点）。
5. （可选）诱导故障或等待真实故障；面板出现路由/提案/Verify。
6. **停止检测** → 监测关闭，恢复授权撤销。
7. 再点 **开始检测** → 仅监测，**不会**自动重新 arm。

证据：`docs/midterm/runs/p0/gui_browser/ops_log.md` + `gui-01`…`gui-04` 截图。

HTTP 对照（非浏览器替代）：

```bash
python3 tools/nx_p0_gui_ops_chain.py \
  --web-url http://127.0.0.1:8001 \
  --control-url http://127.0.0.1:8788 \
  --json-out docs/midterm/runs/p0/gui_ops_chain.json
```

## 4. 强制 4B 闭环（disable_l1，仅对照）

```bash
python3 tools/nx_p0_4b_closed_loop.py \
  --control-url http://127.0.0.1:8788 \
  --llm-url http://127.0.0.1:8080 \
  --execution-mode execute_replay \
  --json-out docs/midterm/runs/p0/4b_closed_loop_live.json
```

## 5. 自然路由

```bash
# A=L1，B=自然 L2+4B（observe；可复现错误提案根因对照）
python3 tools/nx_p0_natural_routing.py \
  --control-url http://127.0.0.1:8788 \
  --llm-url http://127.0.0.1:8080 \
  --execution-mode observe_only \
  --json-out-dir docs/midterm/runs/p0

# 合法自然 L2：冻结帧 → L1 cooldown → L2 restart_camera → Verify
python3 tools/nx_p0_natural_l2_stale.py \
  --control-url http://127.0.0.1:8788 \
  --llm-url http://127.0.0.1:8080 \
  --execution-mode execute_replay \
  --json-out docs/midterm/runs/p0/natural_L2_live_stale.json
```

期望 `natural_L2_live_stale.json`：`disable_l1=false`，`route.selected=L2`，`recovery_outcome=RECOVERED`，`verify_level=function`。

## 6. 启动脚本生命周期（不写 /etc）

```bash
bash deploy/start-edgemedic-agent.sh          # lifecycle_start
bash deploy/start-edgemedic-agent.sh          # 期望拒绝 duplicate，exit 1
curl -s -X POST http://127.0.0.1:8790/shutdown
# 确认 PID 文件清除；kill -9 后可再次 start
```

## 7. systemd（需操作员批准后执行）

模板已校验，**默认未安装**：

```bash
# 审查
cat /home/jetson/Projects/p0-4b-agent/deploy/edgemedic-agent.service
cp deploy/edgemedic-agent.env.example deploy/edgemedic-agent.env
# 编辑：EDGEMEDIC_EXECUTION_MODE=observe_only（生产）或 execute_replay（仅隔离 :8788）

# 安装（需 sudo；会注册系统单元，勿在未确认时指向 :8787）
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

模板校验（不装 /etc）：

```bash
systemd-analyze verify deploy/edgemedic-agent.service
# 期望：无本单元致命错误；etc_unit_absent_ok
```

## 8. 停止隔离实例

```bash
curl -s -X POST http://127.0.0.1:8790/shutdown || kill $(cat /tmp/edgemedic-agent.pid)
kill $(cat /tmp/p0-gearpro-dual.pid)
# 勿杀 :8787/:8000/llama-server（除非另行批准）
```
