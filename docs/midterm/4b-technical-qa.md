# 4B Agent 技术问答（答辩用）

> 阅读分支：`srtp-agent/v2-pressure-pilot`。索引：[README.md](README.md)。

## Q1. 4B 有没有真推理？

有。最终系统验收 `final_system/last_cycle.json`（`L2-725fb29d`）：`model=qwen3-4b`，GBNF，`latency_ms≈3042`，raw=`resume_inspection`。对照：`4b_closed_loop_post_gui.json`。

## Q2. 强制 L2 和自然路由有何区别？

强制闭环用 `disable_l1`。自然路由：L1 无提案时升 L2（`no_l1_or_mem_proposal`）。最终验收用 L1 cooldown 后的第二次 `pause_inspection`，**未**设 `disable_l1`。

## Q3. 最终系统验收如何证明是常驻 Agent？

`tools/nx_p0_final_resident_recover.py` 只 POST `pause_inspection` 并轮询 `:8790/status`。恢复动作由 `edgemedic.service` 的 `monitor_loop`→`run_once` 发出；脚本不调用 Agent `run_once`，不代发 `resume_inspection`。

## Q4. 为何不用 freeze 相机做最终验收？

Freeze  onset 易先触发 `UNKNOWN_*` L2 abstain，占用 30s `L2_COOLDOWN`，与 10s L1 cooldown 窗口错开，常驻路径无法在 cooldown 内完成 L2 执行。Pause 注入是合法隔离故障，且与 4B `resume_inspection` 路径一致。

## Q5. GUI 是否只显示历史 JSON？

否。面板轮询 `/agent/status`。最终验收有浏览器截图与 CDP「路由 L2」观察；停线后武装撤销见 `final-05`。

## Q6. 监测是否等于执行权？

否。start 只开监测；恢复需显式授权且 `execute_replay`。stop → `monitor/stop` 撤权并停监测。

## Q7. Verify=mission 是否等于两模型都好？

需看 specialist 字段与 `verify_dual_audit.json`。`L2-725fb29d` 记录 `verify_level=mission` 且 `recovery_success=true`。

## Q8. systemd / 生产？

模板已校验；**未**装 `/etc`。未改 `:8787`。未部署 9B。
