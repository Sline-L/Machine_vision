# 4B / Agent P0 证据索引

根目录：`docs/midterm/runs/p0/`  
冻结：`docs/midterm/frozen/p0_final_system_2026-09-17.json`

## 最终系统验收（主证据）

| ID | 路径 | 证明 | 判定 |
|----|------|------|------|
| FINAL | `final_system/evidence.json` | GUI arm + 常驻 Agent L2+4B Execute+Verify | PASS |
| FINAL-LC | `final_system/last_cycle.json` | request_id **`L2-725fb29d`** 全字段 | PASS |
| FINAL-GUI | `final_system/final-0*.png` + `ops_log.md` | 浏览器启线/授权/停线 | DONE |
| FINAL-STOP | `final_system/post_stop_disarm_guard.json` | 停线后 monitoring/armed=false | PASS |

## 其它主证据

| ID | 路径 | 证明 | 判定 |
|----|------|------|------|
| CL2 | `4b_closed_loop_post_gui.json` | 强制 L2（disable_l1）对照 | PASS |
| A | `natural_A_l1.json` | 自然 L1 | PASS |
| Bexe | `natural_B_l2_execute.json` | 历史错误提案；Guardian 正确拒绝 | FAIL（正确拦截） |
| Brc | `natural_B_rootcause.json` | 根因全链路 | DONE |
| NL2 | `natural_L2_live_stale.json` | CLI 自然 L2（**非**最终系统验收） | PASS |
| LIFE | `lifecycle_*.json/txt` | 启动脚本生命周期 | DONE |
| SYS | `systemd_analyze_verify.txt` | 模板；`etc_unit_absent_ok` | DONE |

## 源码

| 路径 | 作用 |
|------|------|
| `edgemedic/service.py` | 常驻 Agent |
| `edgemedic/runtime.py` | 路由 / `l2_extra_note` |
| `tools/nx_p0_final_resident_recover.py` | **仅注入 pause**；轮询常驻 Agent |
| `deploy/start-edgemedic-agent.sh` | 启动脚本 |
| `web/src/App.vue` | Agent 面板 |

## 缺口

- `/etc/systemd` 未安装  
- 生产 `:8787` 未 mutate  
- ASR/MTTR 未宣称  
