# GUI 浏览器端到端操作记录

- 时间：2026-09-17（UTC+8）
- 目标：隔离 NX 双专项 Web `http://127.0.0.1:18001/`（SSH LocalForward → NX `:8001`）
- 方式：Cursor IDE Browser（真实页面点击，非 HTTP 替代）
- Agent：`execute_replay` @ `:8790`；Control `:8788`

## 步骤与结果

| 序 | 操作 | 结果 | 证据 |
|----|------|------|------|
| 1 | 打开 GUI；已登录态自动进入主页 | 顶栏服务/相机/模型/Agent/4B 均为绿 | `gui-01-agent-panel.png` |
| 2 | 侧栏查看 EdgeMedic Agent | 服务=在线，4B=就绪，执行模式=`execute_replay`，恢复武装=否 | 同上 |
| 3 | 点击「启用恢复授权」 | `recovery_armed=true`（CDP 轮询 `/agent/status`） | `gui-02-armed.png`，`agent_after_pause.json` |
| 4 | （诱导 pause 后）面板可见路由/提案区 | Agent 仍 armed；本轮无新故障时路由为空 | `agent_after_pause.json` |
| 5 | 点击「停止检测」 | 检测停止；恢复武装撤销为否 | `gui-03-stopped-disarmed.png` |
| 6 | 点击「开始检测」 | `active=true`，`monitoring=true`，`armed=false` | `gui-04-started-monitor-not-armed.png` |

## CDP 核对摘要

停止后再次开始检测：

```json
{"active": true, "monitoring": true, "armed": false}
```

说明：开始产线只启动监测，不会自动 arm；arm 需显式「启用恢复授权」。

## 未用 HTTP 冒充

本目录截图与点击均来自浏览器会话。HTTP 链 `../gui_ops_chain.json` 仅作对照，不替代本验收。
