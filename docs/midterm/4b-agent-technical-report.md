# Qwen3-4B Agent 技术报告（P0 实装）

> 状态：机制已实现；研究级有效性未宣称 ASR/MTTR。
> 证据截止：2026-09-17 NX 隔离双专项 `:8788` + llama-server `:8080`。
> 源码分支：`integration/dual-specialist-edgemedic`（见 git log）。

## 1. 目标与边界

把不可靠小模型（Qwen3-4B）嵌进 GearPro 双专项外围的有界 Agent（EdgeMedic），而非「4B 直接控制 Jetson」。

| 允许 | 禁止 |
|------|------|
| Camera / Locator / Scratch V5 / Missing Hole / Serial / UI / interval | ROS、LiDAR、PX4、9B、生产 `:8787` 未授权 mutate |
| L0/L1 确定性优先；L2 读 Snapshot 出 `{tool,params}` | 绕过 Authority / Guardian / Verify |
| 监测与恢复授权分离 | 默认把生产 Agent 设为 `execute_replay` |

## 2. 实际调用链

```
Replay 双专项 GearPro (:8001 Web / :8788 Control)
        ↑ GET /api/state          ↑ POST /api/action
EdgeMedic Agent (:8790 status)
  L1 Reflex → Memory → L2 Reasoner → Authority → (optional) Execute+Verify
                         ↓
              llama-server Qwen3-4B (:8080)
```

GUI：`inspection/start` → Agent `monitor/start`（**不** arm）；`/agent/recovery/arm`（需操作权且 Agent=`execute_replay`）；`inspection/stop` → `monitor/stop`（撤权+停监测）。

## 3. 案例分离（禁止拼接）

| 案例 | 证据文件 | 路由 | 4B | 执行 | 结果 |
|------|----------|------|----|------|------|
| 强制 L2 闭环 | `runs/p0/4b_closed_loop_post_gui.json` | L2 (`disable_l1`) | 是 | 是 | mission / RECOVERED |
| 自然 L1 | `runs/p0/natural_A_l1.json` | L1 | 否 | 是 | mission / RECOVERED |
| 自然 L2 诊断 | `runs/p0/natural_B_l2_observe.json` | L2 (`no_l1_or_mem_proposal`) | 是 | 否 | Authority AUTO_LOW_RISK |
| 自然 L2 执行 | `runs/p0/natural_B_l2_execute.json` | L2 | 是 | 否* | Guardian 拒绝 `restart_camera`（相机未 STALE） |
| GUI 操作链 | `runs/p0/gui_ops_chain.json` | L1 恢复 | — | 是 | PASS；browser QA NOT_RUN |

\*自然 L2 在现有故障集上能升级并调用 4B；对健康 Replay 相机执行 `restart_camera` 被 Guardian 正确拒绝。**不能**声称「自然 L2→Execute→Verify 全路径已通」；强制 L2 resume 与 GUI 武装后的 L1 resume 是已验证执行路径。

## 4. 4B 真实推理

`4b_inference_snippet.json` / `4b_closed_loop_post_gui.json`：

- model=`qwen3-4b`，GBNF，`latency_ms≈2721`
- raw=`resume_inspection`；Authority=`AUTO_LOW_RISK`
- Control `L2-56dbf807`；Verify=`mission`；`actually_executed=true`

## 5. Verify=mission 的双专项含义

`verify_dual_audit.json`：mission 需 `dual_output_ok`（两专项 loaded + 有效输出/延迟）再升 mission window。闭环后：

- scratch_v5: loaded/infer_ok/last_valid_output + latency≈95ms
- missing_hole_v1: loaded/infer_ok/last_valid_output + latency≈109ms
- `control_view.dual_specialist_mission_verified` 可为 false；**不能**只看字符串，需核对 specialist 字段。

## 6. GUI 联动（实测）

HTTP 操作链 `gui_ops_chain.json` **PASS**：

1. 登录+取得操作权
2. 开始检测 → `monitoring=true`，`recovery_armed=false`，`llm_ready=true`
3. `POST /agent/recovery/arm` → armed（仅 `execute_replay`）
4. 诱导 pause → Agent 执行恢复（本例 L1 resume）→ Verify mission
5. 停止检测 → `monitoring=false`，`recovery_armed=false`

浏览器人工点选：**NOT_RUN**（自动化不可用时以 HTTP 链替代）。

生产默认：Agent `observe_only`；arm 返回 409。

## 7. Agent 服务

- `python -m edgemedic.service`
- PID 防重入；`/recovery/arm|disarm`；llm 未就绪跳过 mutate
- 故障 pause **不会**自动 disarm（否则无法恢复）；**操作员 stop** 才撤权

## 8. systemd（授权范围内）

模板：`deploy/edgemedic-agent.service`（WorkingDirectory=`/home/jetson/Projects/p0-4b-agent`，User=jetson，Restart=on-failure）。

`systemd_template_check.json`：路径/用户/Restart/EnvFile 校验 PASS；`/etc/systemd` **未安装**。

安装命令见演示指南（需操作员批准）。

## 9. 性能

| 段 | 约值 |
|----|------|
| L2 4B | 1.5–3.3 s |
| Control+Verify resume | ~2–4.6 s |

## 10. 未完成

1. 浏览器人工 GUI 验收 NOT_RUN
2. systemd 未写入 `/etc`
3. 自然 L2→Execute→Verify：现有 UNKNOWN 提案在健康相机上被 Guardian 拒绝（正确行为）；缺「真实 STALE/未知故障」现场注入
4. Windows 缺 cv2/httpx/npm；以 NX 测试为准
