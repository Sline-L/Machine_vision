# SystemSnapshot v1

GearPro 对外暴露的结构化世界模型。EdgeMedic 与未来 Web 控制台都读这一份，不直接刮 Qt 或日志。

刷新：全局快照 **2 Hz**；`frame_seq` / `frame_age_ms` 在采集线程更新，快照只拷贝最新值。

## 相对当前代码

| 字段组 | 现状（`srtp` @ 现 HEAD） | v1 要求 |
| --- | --- | --- |
| SYSTEM 资源 | 无 | 新增采样（`psutil` / tegrastats 类） |
| CAMERA `frame_seq` | `LatestFrame._sequence` 已有 | 暴露；增加 `published_at` 才能算 `frame_age_ms` |
| CAMERA FPS / 读失败 | 无独立统计 | 采集线程计数 |
| LOCATOR / V5 分阶段耗时 | 只有整段 `elapsed_ms` | `inspect()` 内打点 |
| SERIAL | `send()` 返回 `(ok, msg)`，无计数 | 累计失败与上次错误 |
| MISSION profile / utility | 无 | 接 InferenceProfile v1 |

没有标注「已有」的字段，**实现快照前必须先做 instrumentation**，禁止用假数据填满 JSON。

## 语义

- 时间：ISO-8601 UTC `timestamp`；时长毫秒除非字段名带 `_s` 或 `_hz`。
- `health`：`[0, 1]`，1 为正常。确定性规则计算，不经 LLM。
- `CAMERA_STALE`（L1，不问 LLM）：`opened` 且 `frame_seq` 在阈值窗口内不增加，或 `frame_age_ms` 超过 `stale_ms`（建议 1000）。
- 依赖：Camera → Locator → Scratch V5 → Verdict；Serial 与 UI 为旁路。某节点 `health` 下降只影响后继，不自动改 profile。

## `health` 建议阈值（可调，须写进配置）

| 节点 | health=1 | 开始下降 | health→0 |
| --- | --- | --- | --- |
| camera | `opened` 且 `frame_age_ms < 200` | age 200–1000 或读失败增加 | 未打开或 stale |
| locator | 已加载且 `latency_ms` 中位 < 40 | 40–120 | 未加载或连续异常 |
| scratch_v5 | 已加载且 `total_latency_ms` 中位 < 80 | 80–200 | 异常或 NaN |
| serial | `connected` 且 `consecutive_failures == 0` | 1–2 次失败 | ≥3 或未连接且任务需要串口 |

## JSON 形状

见 [edgemedic/system-snapshot.schema.json](edgemedic/system-snapshot.schema.json) 与 [edgemedic/examples/system-snapshot.json](edgemedic/examples/system-snapshot.json)。

`locator.backend` 只能是 `pt` 或 `engine`，由当前 `GEARPRO_MODEL1` 后缀决定，不能运行时改字符串而不重建 inspector。

`scratch_v5.profile` 为 InferenceProfile 名。`detector_enabled` 在 CLASSIFY_ONLY 实现前恒为 `true`。

`mission.utility` 见 Profile 文档中的 \(U\)。未实现 profile 时不要填假的 1.0。
