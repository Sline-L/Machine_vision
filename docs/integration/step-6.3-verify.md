# Step 6.3 双专项状态、Verify 与安全仲裁

集成分支 `integration/dual-specialist-edgemedic`。未接入 EdgeMedic / L1 / L2，未开放 Agent 自动恢复。`cap_verify_level` 未删除。

## Guardian 调用链

温度 `>= 80°C`（`thermal_alarm`）→ `Runtime.assert_emergency_hold()`：

1. 置 `_emergency_hold`
2. 首次进入时递增 `_emergency_generation`
3. `apply_to_config(SAFE_STOP)`（失败则直接写 profile）
4. `worker.pause()`

**不获取 `_action_lock`**，因此不会被最长约 75s 的 `rebuild_inspector` 阻塞。

长动作检查点（`rebuild_inspector`）：drop / validate / start / 等待循环均调用 `_abort_rebuild_if_held(generation)`。hold 或 generation 变化则停检并抛错，禁止后续 resume。

解除条件：仅 `execute_action(..., authority="human")` 且 `thermal_alarm` 为假时，`set_inference_profile` 可离开 SAFE_STOP 并清 hold。温度仍高或 agent 权限一律拒绝。

## Snapshot 契约

对外 `/api/v1` / `/api/v2` 仍分别使用 `system-snapshot.v1` / `system-snapshot.v2`。

v2 专项对象**扩展**（兼容加字段）：`loaded`、`infer_ok`、`last_valid_output`、`last_output_frame_seq`、`error_state`。Missing Hole 的 `error_count` **不再**复制共享 worker 计数；不可归因时为 `null` + `error_state=unknown`。`mission.inspection_count` 可选填入。`inference.error_attribution` 标明来源。

Control 内部视图：`gearpro-control-view.v1`（`as_control_view`），不冒充 v2。

观测来源：Worker `load_status`（分阶段加载）、`last_error_source`（locator / scratch_v5 / missing_hole_v1 / unknown）、结果新鲜度（verify 窗口起点帧序 / 时间戳）。

## Verify 逐动作语义

| 动作 | 成功含义 | 升到 function/mission 条件 |
|---|---|---|
| `restart_worker` | 双专项重建并有新输出 | 双专项 loaded + fresh dual output + 窗口 |
| `restart_camera` | 帧恢复；任务恢复另需双专项 | 帧序增长后同样要 dual evidence |
| `resume_inspection` | 检测恢复 | hold 禁止；dual evidence 才记恢复 |
| `pause_inspection` | 已停检 | mission = 停检目标，不是检测恢复 |
| `SAFE_STOP` | 安全停机 | mission；`recovery_success` 仍为 false |
| `apply_settings` | 配置生效 | 固定 config，不升任务恢复 |

`accepted` / `executed` / `config_verified` / `function_verified` / `mission_verified` / `recovery_success` 分字段返回。`recovery_success` 仅 `inspection_recovery_success`：恢复类动作 + function/mission + `dual_specialist_evidence`。

## cap_verify_level

保留。证据充足（`dual_specialist_evidence`）时放行；不足则 function/mission 降为 config。SAFE_STOP / pause / reconnect_serial 等非“检测恢复”动作不因 dual 缺失而降级。紧急 hold 时恢复类结果不得升到 RECOVERED。

## 测试分层

- 安全并发：`tests/test_guardian_concurrency.py`（Event 同步）
- Snapshot / Verify / 回归：见 unittest discover
- 实模型加载：无 PyTorch 时 skip，不记 ERROR
- 路径假设：`Path` / `samefile`，不再硬编码分隔符或短路径字符串
