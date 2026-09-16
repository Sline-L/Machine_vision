# Step 6.2 Control 接入记录

集成分支 `integration/dual-specialist-edgemedic`。未接入 EdgeMedic / L1 / L2。未宣称事务式回滚。

## 调用链

Web lease（`SessionManager.owns_control`）→ `runtime.human_action`（服务器赋值 `authority=human`）→ `ControlService.run_action` → `actions.accept` → `execute_action` → 内部 `gearpro-control-view.v1` 上的 `verify.assess`，再经 `cap_verify_level` 将双专项恢复动作的 function/mission 降为 config。`recovery_success` 仅在 function/mission，故被 cap 后不为真。

本机 HTTP Control 默认 `127.0.0.1:8787`，`authority=agent`。`bind_source` 将客户端自称的 `human` 降为 `reflex`。

## Web 变更入口

经 lease + Control：`/inspection/start|stop`、`/source/camera|video`、`/settings`、`/stats/reset`（v1 与 v2 同路径）。

未接到 Web、仅 Control 白名单：`restart_camera`、`restart_worker`、`reconnect_serial`、`set_inference_profile`、`set_locator_profile`、`reload_config`、`rollback_config`、`get_state`。HUMAN_ONLY：`apply_settings`、`use_camera`、`use_video`、`reset_stats`。

## Verify 限制

旧 `gp/verify.py` 仍只读 `scratch_v5`。对外 `/api/v2` health 仍是 `system-snapshot.v2`。Control 使用 `as_control_view()`，schema 为 `gearpro-control-view.v1`，不是 v2。不得把 accepted 或 config_verified 记成 RECOVERED。

## Guardian

`thermal_stop_needed` ≥80°C 设置 `_emergency_hold` 并切 SAFE_STOP。温度仍高或非 human 时拒绝离开 SAFE_STOP / resume。人工且温度已降可切回 FULL/SPARSE 并清除 hold。未改温度阈值。

## Last-good

`config_verified` 且动作在 `LKG_ACTIONS` 时调用 `persist_last_known_good`。进程内 `_config_backup` 支持 `rollback_config`。未做完整双专项模型重载回滚验证，不得称为事务恢复。

## 双专项重建

`restart_worker` → `rebuild_inspector`：`drop_inspector` → `validate_models`（双专项 fail-closed）→ 条件 resume。`TRT_FAST` / `CLASSIFY_ONLY` / `LOCATE_ONLY` 由 `profiles.apply_to_config` 拒绝。`set_locator_profile` 本阶段未启用（`locator_path_for` 抛错）。
