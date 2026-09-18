# P0 最终系统级验收操作记录

- 时间：2026-09-17
- 隔离：NX Replay Web `:8001` / Control `:8788` / Agent `:8790` / llama-server `:8080`
- 隧道：`http://127.0.0.1:18001/`
- 主 request_id：`L2-725fb29d`

## 步骤

1. GUI 产线已在运行（「停止检测」可见）；Agent `execute_replay`，`monitoring=true`。
2. 浏览器点击「启用恢复授权」→ `recovery_armed=true`（截图 `final-01-armed.png` / `final-02-rearmed.png`）。
3. 测试脚本 **仅** `POST pause_inspection` 两次（`tools/nx_p0_final_resident_recover.py`），**不**调用 `run_once`、**不**代发 `resume_inspection`。
4. 常驻 `edgemedic.service`：
   - 第一次 pause → L1 `resume_inspection`（`L1-INSPECTION_PAUSED-9a7c0116`，Verify=mission）
   - 第二次 pause（L1 cooldown 内）→ L2 + 真实 Qwen3-4B → `resume_inspection` → Authority AUTO_LOW_RISK → Control Execute → Verify=**mission** / RECOVERED（`L2-725fb29d`）
5. GUI Agent 面板绑定 `last_cycle`（路由/提案/Authority/Verify/已执行）；CDP 曾读到「路由 L2」；截图 `final-04-gui-l2-route.png` 显示面板恢复字段。
6. GUI「停止检测」→ `monitoring=false`，`recovery_armed=false`（`final-05-stopped-disarmed.png`，`post_stop_disarm_guard.json`）。

## 同 request_id 证据索引（L2-725fb29d）

| 产物 | 路径 |
|------|------|
| 全链路证据 | `evidence.json` |
| last_cycle（4B/Authority/Control/Verify） | `last_cycle.json` |
| Phase A L1 | `phase_a_l1_cycle.json` |
| Agent 服务日志切片 | `agent_service.log_slice.txt` |
| GUI 截图 | `final-0*.png` |

## 明确未做

- 未安装 `/etc/systemd`
- 未改生产 `:8787`
- 未部署 9B
