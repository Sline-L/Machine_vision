# GearPro Web API v1

API 前缀为 `/api/v1`。除会话状态和登录外，接口均要求 `gearpro_session` Cookie；改变
运行状态的接口还要求当前会话持有操作员控制锁。

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `GET` | `/session` | 查询是否登录及是否需要密码 |
| `POST` | `/session/login` | 使用共享密码登录 |
| `POST` | `/session/logout` | 注销并释放本会话的控制权 |
| `GET` | `/state` | 获取完整运行快照 |
| `WS` | `/events` | 每 0.5 秒接收运行快照并发送控制心跳 |
| `GET` | `/stream?view=auto` | 获取 MJPEG 原图或标注流 |
| `POST` | `/control/acquire` | 取得单操作员控制锁 |
| `POST` | `/control/release` | 主动释放控制锁 |
| `POST` | `/inspection/start` | 开始或恢复检测 |
| `POST` | `/inspection/stop` | 暂停检测但保留已加载模型 |
| `POST` | `/source/camera` | 切回实时相机并启用串口 |
| `POST` | `/source/video` | 以 multipart 字段 `file` 上传并检测视频 |
| `PUT` | `/settings` | 校验、应用并保存运行参数 |
| `POST` | `/stats/reset` | 清空本次内存统计与最近结果 |

WebSocket 客户端持有控制权时每 10 秒发送：

```json
{"type": "control_heartbeat"}
```

`view` 可取 `auto`、`raw` 或 `annotated`。`auto` 在检测运行且已有结果时返回标注图，
否则返回原图。

常见响应码：`400` 参数错误、`401` 未登录、`413` 上传超限、`423` 未取得控制权或控制权
已被其他终端占用。生产网络若不可信，应由反向代理终止 HTTPS，并限制可访问来源。
