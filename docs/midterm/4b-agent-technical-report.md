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
| 自然 L2 错误提案（历史） | `runs/p0/natural_B_l2_execute.json` + `natural_B_rootcause.json` | L2 | 是 | 否 | Guardian 拒绝健康机 `restart_camera` |
| 自然 L2 提示修复后 | `runs/p0/natural_B_rootcause_after_hint.json` | L2 | 是 | 否 | 4B `tool=null` abstain |
| 自然 L2 合法执行 | `runs/p0/natural_L2_live_stale.json` | L2（L1 cooldown，非 disable_l1） | 是 | 是 | function / RECOVERED |
| GUI 浏览器 E2E | `runs/p0/gui_browser/` | — | — | — | 登录→arm→停线撤权→再开监测 |

## 4. 自然 L2 错误提案根因（`natural_B_l2_execute.json`）

**输入**：合成 overlay `L2_unknown_scratch`（scratch_health=0.1，相机 opened/health=1.0/age=40ms）；Control Guardian 评估的是 **LIVE :8788 Replay** 健康相机。

| 阶段 | 事实 |
|------|------|
| 故障分类 | `UNKNOWN_SCRATCH_V5`（L1 无对应动词） |
| 旧 Prompt hint | 无条件 `"Prefer restart_camera for stale camera..."` |
| 4B 原始输出 | `{"tool":"restart_camera","params":{}}` |
| Authority | `AUTO_LOW_RISK` / `would_execute=true` |
| Guardian | `accepted=false`，`"摄像头未处于失败或 STALE，拒绝 restart_camera"` |

**根因**：误导性 L2 hint + overlay/live 相机语义不一致 → 4B 对健康相机提案 `restart_camera`。Guardian 正确拦截；**未**削弱 Guardian，**未**用 `disable_l1=true` 冒充自然路由。

**修复**：`edgemedic.runtime.l2_extra_note` 按 Snapshot 条件化——`UNKNOWN_*` 且相机未 stale 时明确禁止 hint `restart_camera`。修复后同 overlay：`tool=null`，Authority=`OBSERVE`。

**合法自然 L2 全路径**：`GEARPRO_RESEARCH_INJECT` 冻结帧 → `CAMERA_STALE`；L1 进入 cooldown 后自然落到 L2（`disable_l1=false`）；4B 提案 `restart_camera`；Replay 允许 restart（`allow_restart_camera`）；Verify=`function`，`RECOVERED`（见 `natural_L2_live_stale.json`）。

## 5. 4B 真实推理（强制闭环对照）

`4b_inference_snippet.json` / `4b_closed_loop_post_gui.json`：

- model=`qwen3-4b`，GBNF，`latency_ms≈2721`
- raw=`resume_inspection`；Authority=`AUTO_LOW_RISK`
- Control `L2-56dbf807`；Verify=`mission`；`actually_executed=true`

## 6. Verify=mission 的双专项含义

`verify_dual_audit.json`：mission 需 `dual_output_ok`（两专项 loaded + 有效输出/延迟）再升 mission window。闭环后：

- scratch_v5: loaded/infer_ok/last_valid_output + latency≈95ms
- missing_hole_v1: loaded/infer_ok/last_valid_output + latency≈109ms
- `control_view.dual_specialist_mission_verified` 可为 false；**不能**只看字符串，需核对 specialist 字段。

## 7. GUI 联动（浏览器实测）

浏览器 E2E（`runs/p0/gui_browser/ops_log.md` + 四张截图）：

1. 登录进入主页；Agent 面板显示在线 / 4B 就绪 / `execute_replay` / 未武装
2. 点击「启用恢复授权」→ armed
3. 停止检测 → 监测关闭且撤权
4. 开始检测 → `monitoring=true`，`armed=false`（开线不自动 arm）

HTTP 链 `gui_ops_chain.json` 仅作对照，**不**替代浏览器验收。

生产默认：Agent `observe_only`；arm 返回 409。

## 8. Agent 服务生命周期

启动脚本 `deploy/start-edgemedic-agent.sh`（默认 `observe_only`；拒绝对 `:8787` 的 `execute_replay`）：

| 检查 | 证据 | 结果 |
|------|------|------|
| 启动 | `lifecycle_start.json` | `ok=true`，`llm_ready=true` |
| 重复启动 | `lifecycle_dup.txt` | exit=1，拒绝 duplicate |
| 异常退出恢复 | kill -9 后重启 | PID 可重建（脚本防重入） |
| 停止 | `lifecycle_shutdown.json` + `lifecycle_stop.txt` | shutdown ok，`PID_CLEARED` |

## 9. systemd（授权范围内）

模板：`deploy/edgemedic-agent.service`（WorkingDirectory=`/home/jetson/Projects/p0-4b-agent`，User=jetson，Restart=on-failure）。

- `systemd_template_check.json`：路径/用户/Restart/EnvFile 校验 PASS
- `systemd_analyze_verify.txt`：`systemd-analyze verify` 对模板可跑；系统无关警告来自既有单元；**`etc_unit_absent_ok`**
- `/etc/systemd` **未安装**；正式 enable 需单独授权

## 10. 性能

| 段 | 约值 |
|----|------|
| L2 4B | 1.5–3.3 s |
| Control+Verify resume | ~2–4.6 s |
| 自然 L2 stale restart | Verify=function |

## 11. 未完成 / 未授权

1. systemd **未**写入 `/etc`、未 enable 开机自启
2. 生产 `:8787` 未做 mutate
3. Windows 缺部分运行时依赖时以 NX 证据为准
4. 研究级 ASR/MTTR **未**验证
