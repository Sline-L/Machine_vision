# 4B / Agent P0 证据索引

根目录：`docs/midterm/runs/p0/`
NX：`/home/jetson/Projects/p0-4b-agent/docs/midterm/runs/p0/`

## 主证据

| ID | 路径 | 证明 | 判定 |
|----|------|------|------|
| CL2 | `4b_closed_loop_post_gui.json` | 强制 L2→Authority→Execute→Verify | PASS |
| SNIP | `4b_inference_snippet.json` | 4B raw/latency/Authority | PASS |
| GUI | `gui_ops_chain.json` | GUI HTTP 操作链；browser NOT_RUN | PASS |
| A | `natural_A_l1.json` | 自然 L1 + mission Verify | PASS |
| Bobs | `natural_B_l2_observe.json` | 自然 L2 + 真实 4B + Authority | PASS |
| Bexe | `natural_B_l2_execute.json` | 自然 L2 执行被 Guardian 拒绝 | FAIL（预期行为） |
| VFY | `verify_dual_audit.json` | mission 双专项字段审计 | PASS |
| SYS | `systemd_template_check.json` | unit 字段校验；未装 /etc | PASS |
| AGX | `agent_status_execute_replay.json` | 隔离 Agent execute_replay 未 arm | PASS |

## 案例分离

| 文件 | 说明 |
|------|------|
| `demo_C_4b_diagnose.json` | 4B 诊断，未执行 |
| `demo_E_l1_recover.json` | L1 恢复，无 4B |

## 源码

| 路径 | 作用 |
|------|------|
| `edgemedic/service.py` | Agent 服务 + arm/disarm |
| `edgemedic/runtime.py` | 路由 / Authority 保留 |
| `gp/web.py` | Agent 代理与产线通知 |
| `web/src/App.vue` | Agent 面板 |
| `tools/nx_p0_4b_closed_loop.py` | 强制 L2 闭环 |
| `tools/nx_p0_natural_routing.py` | 自然 L1/L2 |
| `tools/nx_p0_gui_ops_chain.py` | GUI HTTP 链 |
| `deploy/edgemedic-agent.service` | systemd 模板 |

## 明确缺口

- 浏览器人工 GUI：**NOT_RUN**
- 自然 L2→Execute→Verify 全路径：无合适现场故障（Guardian 拒健康机 `restart_camera`）
- systemd：**未** enable 到开机自启
