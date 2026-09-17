# 4B / Agent P0 证据索引

根目录：`docs/midterm/runs/p0/`
NX：`/home/jetson/Projects/p0-4b-agent/docs/midterm/runs/p0/`

## 主证据

| ID | 路径 | 证明 | 判定 |
|----|------|------|------|
| CL2 | `4b_closed_loop_post_gui.json` | 强制 L2→Authority→Execute→Verify | PASS |
| SNIP | `4b_inference_snippet.json` | 4B raw/latency/Authority | PASS |
| GUI-HTTP | `gui_ops_chain.json` | GUI HTTP 操作链（对照） | PASS |
| GUI-BR | `gui_browser/ops_log.md` + `gui-0*.png` | **真实浏览器**登录/arm/停线/再开监测 | DONE |
| A | `natural_A_l1.json` | 自然 L1 + mission Verify | PASS |
| Bobs | `natural_B_l2_observe.json` | 自然 L2 + 真实 4B + Authority | PASS |
| Bexe | `natural_B_l2_execute.json` | 历史错误提案；Guardian 拒健康机 restart | FAIL（正确拦截） |
| Brc | `natural_B_rootcause.json` | Snapshot/分类/hint/4B/Authority/Guardian 全链路 | DONE |
| Bfix | `natural_B_rootcause_after_hint.json` | 条件化 hint 后 4B abstain | DONE |
| NL2 | `natural_L2_live_stale.json` | 自然 L2（L1 cooldown）+ Execute + Verify=function | PASS |
| VFY | `verify_dual_audit.json` | mission 双专项字段审计 | PASS |
| LIFE | `lifecycle_*.json/txt` | 启动/重复启动/停止 | DONE |
| SYS | `systemd_template_check.json` + `systemd_analyze_verify.txt` | unit 校验；`etc_unit_absent_ok` | DONE |
| AGX | `agent_status_execute_replay.json` | 隔离 Agent execute_replay 未 arm | PASS |

## 案例分离

| 文件 | 说明 |
|------|------|
| `demo_C_4b_diagnose.json` | 4B 诊断，未执行 |
| `demo_E_l1_recover.json` | L1 恢复，无 4B |
| `natural_B_l2_execute.json` | **不得**再标为自然 L2 全路径成功 |
| `natural_L2_live_stale.json` | 合法自然 L2 全路径证据 |

## 源码

| 路径 | 作用 |
|------|------|
| `edgemedic/service.py` | Agent 服务 + arm/disarm |
| `edgemedic/runtime.py` | `l2_extra_note` 条件化 hint；路由 / Authority |
| `gp/runtime.py` | Replay 允许 `restart_camera`（非 file-video） |
| `gp/web.py` | Agent 代理与产线通知 |
| `web/src/App.vue` | Agent 面板 |
| `tools/nx_p0_4b_closed_loop.py` | 强制 L2 闭环 |
| `tools/nx_p0_natural_routing.py` | 自然 L1/L2 |
| `tools/nx_p0_natural_l2_stale.py` | 自然 L2 stale 恢复 |
| `tools/nx_p0_gui_ops_chain.py` | GUI HTTP 链（对照） |
| `deploy/start-edgemedic-agent.sh` | 启动脚本（默认 observe_only） |
| `deploy/edgemedic-agent.service` | systemd 模板 |

## 明确缺口

- systemd：**未**写入 `/etc`、未 enable 开机自启（需单独授权）
- 生产 `:8787`：未授权 mutate
- 研究级 ASR/MTTR：未宣称
