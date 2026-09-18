# 4B Agent 演示指南（可复现）

> 阅读分支：`srtp-agent/v2-pressure-pilot`。索引：[README.md](README.md)。

隔离：NX `p0-gearpro-dual`（`:8001`/`:8788`）+ `p0-4b-agent` + llama-server `:8080`。  
**禁止**对生产 `:8787` 使用 `execute_replay`。

隧道：`ssh -L 18001:127.0.0.1:8001 -L 18790:127.0.0.1:8790 jetson@192.168.55.2`  
浏览器：`http://127.0.0.1:18001/`

## 1. 启动隔离双专项

```bash
cd /home/jetson/Projects/p0-gearpro-dual
nohup env GEARPRO_REPLAY_DIR=/home/jetson/Projects/p0-gearpro-dual/tests/replay/frames \
  GEARPRO_RESEARCH_INJECT=1 \
  EDGEMEDIC_STATUS_URL=http://127.0.0.1:8790 \
  .venv/bin/python3 -m gp --host 127.0.0.1 --port 8001 --control-port 8788 \
  >/tmp/p0-gearpro-dual.log 2>&1 &
```

## 2. 启动常驻 Agent（隔离 execute_replay；默认不 arm）

```bash
cd /home/jetson/Projects/p0-4b-agent
export EDGEMEDIC_EXECUTION_MODE=execute_replay
export EDGEMEDIC_CONTROL_URL=http://127.0.0.1:8788
bash deploy/start-edgemedic-agent.sh
# 或：python3 -m edgemedic.service --control-url http://127.0.0.1:8788 \
#      --llm-url http://127.0.0.1:8080 --execution-mode execute_replay \
#      --pidfile /tmp/edgemedic-agent.pid --auto-monitor
```

## 3. GUI（必须浏览器）

1. 登录并取得操作权。  
2. **开始检测** → 监测中；恢复武装=否。  
3. **启用恢复授权**。  
4. 保持页面打开以观察 Agent 面板（路由/提案/Verify）。

## 4. P0 最终系统验收（注入暂停，常驻 Agent 恢复）

```bash
# 仅 pause_inspection；禁止对本脚本改为调用 run_once
python3 tools/nx_p0_final_resident_recover.py
# 期望 RESULT PASS request_id=L2-...
# 证据写入 docs/midterm/runs/p0/final_system/
```

然后 GUI **停止检测** → 确认监测关闭且恢复武装撤销。

## 5. 对照实验（非最终验收）

```bash
# 强制 disable_l1 闭环（对照）
python3 tools/nx_p0_4b_closed_loop.py --control-url http://127.0.0.1:8788 \
  --llm-url http://127.0.0.1:8080 --execution-mode execute_replay \
  --json-out docs/midterm/runs/p0/4b_closed_loop_live.json

# CLI 自然 L2 stale（不得替代常驻服务验收）
python3 tools/nx_p0_natural_l2_stale.py --control-url http://127.0.0.1:8788 \
  --llm-url http://127.0.0.1:8080 --execution-mode execute_replay \
  --json-out docs/midterm/runs/p0/natural_L2_live_stale.json
```

## 6. systemd（需批准；默认未装）

见单元 `deploy/edgemedic-agent.service`。`systemd-analyze verify` 可跑；**勿**未经授权 `cp` 到 `/etc/systemd`。

## 7. 停止隔离

```bash
curl -s -X POST http://127.0.0.1:8790/shutdown || kill $(cat /tmp/edgemedic-agent.pid)
# 勿杀 :8787/:8000/llama-server
```
