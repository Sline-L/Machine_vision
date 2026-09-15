# GearPro Web API v2

新客户端使用 `/api/v2`。`/api/v1` 暂时保留一个发布周期，认证 Cookie 和单操作员控制锁在两个版本间共享。

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `GET` | `/session` | 查询登录状态 |
| `POST` | `/session/login`、`/session/logout` | 登录或注销 |
| `GET` | `/state` | 获取完整运行状态 |
| `WS` | `/events` | 每 0.5 秒接收状态并发送控制心跳 |
| `GET` | `/stream?view=auto` | 获取 MJPEG 原图或标注流 |
| `POST` | `/control/acquire`、`/control/release` | 获取或释放操作权 |
| `POST` | `/inspection/start`、`/inspection/stop` | 启停检测 |
| `POST` | `/source/camera`、`/source/video` | 切换相机或上传视频 |
| `PUT` | `/settings` | 校验、应用并保存设置 |
| `POST` | `/stats/reset` | 清空内存统计和最近结果 |

表中的路径分别拼接 `/api/v2` 或兼容期内的 `/api/v1`。除会话状态和登录外，接口都要求 `gearpro_session` Cookie；改变运行状态的接口还要求当前会话持有控制锁。

## v2 检测结果

`state.result` 以双专项 OR 为最终判定：

```json
{
  "verdict": "不合格",
  "has_gear": true,
  "is_defective": true,
  "reject_reasons": ["missing_hole"],
  "model_versions": {"scratch": "scratch_v5", "missing_hole": "missing_hole_v1"},
  "observations": [
    {
      "box": [10, 20, 300, 310],
      "location_confidence": 0.94,
      "is_defective": true,
      "reject_reasons": ["missing_hole"],
      "specialists": {
        "scratch": {
          "probability": 0.12,
          "threshold": 0.300273610279458,
          "reject": false,
          "classifier_probability": 0.18,
          "detector_probability": 0.10,
          "auxiliary_box": null
        },
        "missing_hole": {
          "probability": 0.73,
          "threshold": 0.3413327979078584,
          "reject": true,
          "classifier_probability": 0.81,
          "detector_probability": 0.65,
          "auxiliary_box": [40, 50, 90, 100]
        }
      }
    }
  ]
}
```

每个专项使用自己的概率和阈值。客户端应读取 `is_defective` 或 `reject`，不能把两个概率合并后再使用单一阈值。

v2 设置字段为 `scratch_threshold` 和 `missing_hole_threshold`，`model_default_thresholds` 提供恢复默认值所需的只读值。

## v1 兼容规则

- v1 的 `verdict`、`is_defective` 和统计反映双专项最终 OR 判定。
- `defect_score`、`classifier_probability`、`detector_probability` 和 `defect_threshold` 保持 Scratch V5 语义。
- v1 结果包含 `compatibility_notice`。旧客户端不能再根据 `defect_score` 自行计算最终判定。
- v1 设置中的 `defect_threshold` 映射到 v2 的 `scratch_threshold`。

WebSocket 客户端持有控制权时每 10 秒发送 `{"type":"control_heartbeat"}`。常见响应码为 `400` 参数错误、`401` 未登录、`413` 上传超限、`423` 未取得控制权。
