# Qwen3-4B Agent 技术报告（P0 实装）

> 状态：机制已实现；研究级有效性未宣称 ASR/MTTR。
> 证据截止：2026-09-17 NX 隔离双专项 `:8788` + llama-server `:8080`。
> 冻结：`docs/midterm/frozen/p0_final_system_2026-09-17.json`
> 源码分支：`integration/dual-specialist-edgemedic`

## 1. 目标与边界

把不可靠小模型（Qwen3-4B）嵌进 GearPro 双专项外围的有界 Agent（EdgeMedic），而非「4B 直接控制 Jetson」。

| 允许 | 禁止 |
|------|------|
| Camera / Locator / Scratch V5 / Missing Hole / Serial / UI / interval | ROS、LiDAR、PX4、9B、生产 `:8787` 未授权 mutate |
| L0/L1 确定性优先；L2 读 Snapshot 出 `{tool,params}` | 绕过 Authority / Guardian / Verify |
| 监测与恢复授权分离 | 默认把生产 Agent 设为 `execute_replay` |

## 2. P0 最终系统级验收（唯一闭环）

隔离 Replay + GUI + **常驻** `edgemedic.service`（非 CLI `run_once`）：

| 步骤 | 结果 | 证据 |
|------|------|------|
| GUI 启产线 → Agent monitoring | 是 | `final_system/ops_log.md` |
| GUI 显式启用恢复授权 | `recovery_armed=true` | `final-01/02-*.png` |
| 脚本仅注入 `pause_inspection` | 不调用 Agent `run_once` | `nx_p0_final_resident_recover.py` |
| 常驻 Agent 自然 L2 + 真实 4B | `resume_inspection` | `last_cycle.json` |
| Authority → Control → Execute → Verify | mission / RECOVERED | request_id **`L2-725fb29d`** |
| GUI 显示诊断/动作 | 面板绑定 `last_cycle`；CDP 见路由 L2 | `final-04-gui-l2-route.png` |
| 停止产线自动撤权 | `monitoring=false`，`armed=false` | `final-05` + `post_stop_disarm_guard.json` |

Freeze 注入路径曾因 `UNKNOWN_*` 误触发 L2 abstain（占用 30s `L2_COOLDOWN`）与 10s L1 cooldown 窗口不重叠而失败；最终合法注入为 Control `pause_inspection`（脚本只造故障，恢复由常驻 Agent 完成）。

## 3. 调用链

```
Replay 双专项 GearPro (:8001 Web / :8788 Control)
        ↑ GET /api/state          ↑ POST /api/action
EdgeMedic Agent (:8790 status)  ← GUI /agent/* 代理
  L1 Reflex → Memory → L2 Reasoner → Authority → Execute+Verify
                         ↓
              llama-server Qwen3-4B (:8080)
```

## 4. 案例分离（禁止拼接）

| 案例 | 证据 | 说明 |
|------|------|------|
| **最终系统验收** | `runs/p0/final_system/` | 常驻 Agent + GUI + 真实 4B |
| 强制 L2 闭环 | `4b_closed_loop_post_gui.json` | `disable_l1` 对照 |
| 自然 L1 | `natural_A_l1.json` | 无 4B |
| 历史错误提案 | `natural_B_l2_execute.json` | Guardian 拒健康机 restart |
| 合法自然 L2（CLI） | `natural_L2_live_stale.json` | **不得**替代最终系统验收 |

## 5. `L2-725fb29d` 摘要

- fault=`INSPECTION_PAUSED`；route=L2；`disable_l1=false`；why=`no_l1_or_mem_proposal`
- 4B raw=`resume_inspection`；model=`qwen3-4b`；latency_ms≈3042
- Authority=`AUTO_LOW_RISK`；Control accepted/executed；Verify=`mission`；outcome=`RECOVERED`

## 6. systemd / 生产

模板已校验；**未**写入 `/etc`。生产 `:8787` 未 mutate。Agent 启动脚本默认 `observe_only`。

## 7. 未完成

1. systemd 正式安装需单独授权  
2. 研究级 ASR/MTTR 未验证  
3. 9B 未部署（按要求）
