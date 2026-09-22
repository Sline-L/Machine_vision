# InferenceProfile v1

Agent 与人工只切换**命名档位**，不直接拧几十个内部旋钮。切换必须走：停 worker → 释放 inspector（若定位后端变化）→ 应用配置 → 重建/warmup（若需要）→ health check → resume。失败 rollback 到 `rollback_target`。

## 相对当前代码（禁止写假接口）

当前 `TwoStageInspector` **每次**跑 Locator + V5 两路分类 + P2 检测（`imgsz=960`）。`AppConfig.inference_interval` 与 `inference_profile` 存在。定位 `.pt`/`.engine` 只在进程启动时加载。Camera 采集与 Qt 预览已拆成两个定时器。

因此：

| 能力 | v1 是否允许写进 API |
| --- | --- |
| 改 `inference_interval` | 可以，现有字段 |
| 停/开检测 worker | 可以，现有 start/stop |
| 定位切 `.engine` | 可以，但是 **重建 inspector**，不是赋值 `backend` |
| 关闭 P2、只分类 | **先改 `ScratchV5Runtime.predict`**，再开放 CLASSIFY_ONLY |
| 关掉两路分类（LOCATE_ONLY） | **先改 `inspect()`** |
| P2 960→640/768 | **不做**。权重与配置写死 960，改尺寸不是 runtime 开关 |
| 独立 UI FPS | 采集定时器与 `preview_timer` 已分开；`ui_refresh_hz` 默认 15 |

## 档位

| name | locator | classifiers | P2 detector | interval_s | 实现状态 | mission_quality \(Q_D\) |
| --- | --- | --- | --- | --- | --- | --- |
| `FULL` | 启动时的 pt 或 engine | 开 | 开 960 | 0.10 | 即当前默认 | 1.00 |
| `TRT_FAST` | `model1.engine` | 开 | 开 960 | 0.10 | 需重建 inspector；缺文件则拒绝 | 1.00 |
| `SPARSE` | 保持当前 locator | 开 | 开 960 | 0.20 | 已实现：改 interval | 0.90 |
| `CLASSIFY_ONLY` | 保持当前 locator | 开 | **跳过前向**；`defect_score` = 分类均值（融合 \(\alpha=1\)） | 0.20 | **未实现** | 0.65 |
| `LOCATE_ONLY` | 保持当前 locator | 关 | 关 | 0.30 | **未实现** | 0.20 |
| `SAFE_STOP` | 不推理 | 关 | 关 | — | 已实现：停 worker | 0.00 |

`TRT_FAST` 与 `FULL` 的检测质量相同，差在延迟；\(Q_D\) 同为 1.0。Mission Utility：

\[
U = 0.3\,Q_L + 0.5\,Q_D + 0.2\,Q_S
\]

- \(Q_L\)：locator 已加载且近期有成功 `predict` 则为 1，否则 0。
- \(Q_D\)：上表。
- \(Q_S\)：串口最近一次发送成功或任务未启用串口则为 1，否则 0。

`FULL` 的 rollback 是自身（no-op）。`TRT_FAST` rollback → `FULL`（若 FULL 用的是 pt）。`SPARSE` rollback → 进入 SPARSE 前的档位。`SAFE_STOP` rollback → 进入前的档位。

未实现的档位：`set_inference_profile` 必须返回错误，不得静默当成 FULL。

JSON： [edgemedic/inference-profile.schema.json](edgemedic/inference-profile.schema.json)。
