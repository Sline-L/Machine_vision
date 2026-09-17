# 4B Agent 技术问答（答辩用）

## Q1. 4B 有没有真推理？

有。`4b_closed_loop_post_gui.json`：`model=qwen3-4b`，GBNF，`latency_ms≈2721`，raw 含 `resume_inspection`。自然升级见 `natural_B_l2_observe.json`。

## Q2. 强制 L2 和自然路由有何区别？

强制闭环用 `disable_l1` 证明 4B→Authority→Execute→Verify。自然路由：`natural_A_l1` 证明简单故障走 L1；`natural_B` 证明 `UNKNOWN_*` 无 L1 时自然进 L2 并调 4B。二者分文件，不拼接。

## Q3. 自然 L2 执行为何 FAIL？

4B 提案 `restart_camera`，Authority 批准，但 Control/Guardian 在相机未 STALE 时拒绝（`摄像头未处于失败或 STALE`）。这是安全机制，不是测试造假失败。完整「自然 L2 执行+Verify」需真实 STALE/未知现场；当前未宣称已验证。

## Q4. GUI 是否只显示历史 JSON？

否。面板每 2s 拉 `/api/v1/agent/status` 代理实时 `:8790`。`gui_ops_chain.json` 覆盖 start→arm→恢复→stop。浏览器人工点选仍为 NOT_RUN。

## Q5. 监测是否等于执行权？

否。start 只开监测；恢复需显式「启用恢复授权」，且 Agent 必须是隔离 `execute_replay`。stop 撤权并停监测。

## Q6. Verify=mission 是否等于两模型都好？

需看 specialist 字段。`verify_dual_audit.json` 显示闭环后 scratch/missing 均 `loaded/infer_ok/last_valid_output` 且有 latency。不能只念 `verify_level` 字符串。

## Q7. systemd 部署了吗？

模板已校验路径/用户/Restart；**未**写入 `/etc`。安装/回滚命令见 `4b-demo-guide.md`，需批准。

## Q8. 生产安全？

脚本拒绝 `:8787`+`execute_replay`。生产 Agent 默认 `observe_only`，arm 返回 409。本次只操作隔离 `:8788`。
