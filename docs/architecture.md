# GearPro Web 系统架构

## 1. 总体结构

GearPro Web 是单设备、单检测流水线的局域网服务。FastAPI 负责登录、控制、状态推送、
视频上传和静态页面；模型、相机和串口由独立于浏览器连接的 `GearProRuntime` 管理。

```text
电脑 / 平板浏览器
  ├─ Vue 静态页面
  ├─ WebSocket 状态（2 Hz）
  ├─ MJPEG 画面（最高 10 FPS）
  └─ HTTP 控制与视频上传
             │
             ▼
        FastAPI / Uvicorn
             │
             ▼
       GearProRuntime
  ├─ CameraCapture ──► LatestFrame
  ├─ InspectionWorker ──► TwoStageInspector
  ├─ InspectionStats
  ├─ SerialOutput
  └─ JPEG 缓存
```

浏览器不是检测任务的所有者。页面刷新、断线或关闭只影响该客户端，后台任务继续运行。

## 2. 线程与数据流

- 相机线程通过 OpenCV V4L2 采集，只保存最新帧，不建立积压队列。
- 推理线程在第一次启动检测时加载 Model1 和 Scratch V5，之后暂停和恢复都复用模型。
- 相机模式按推理间隔获取最新未处理帧；视频模式按原视频顺序和帧率处理。
- 推理结果写入最新标注帧和共享状态，再执行冷却计数与串口输出。
- Web 事件循环不运行 OpenCV 或模型推理；慢客户端不会阻塞采集和检测。
- 原图与标注图分别缓存一次 JPEG，多客户端共享编码结果。

模型异常、空 ROI、NaN/Inf 和 CUDA OOM 会停止当前检测并进入错误状态。错误结果不参与
统计，也不会发送串口 `01`。

## 3. 模型与业务行为

Model1 对整帧定位齿轮，Scratch V5 对每个 ROI 执行两个分类器和一个划痕检测器：

```text
defect_score = 0.25 × ((classifier_1 + classifier_2) / 2)
             + 0.75 × detector_probability
```

同一帧多个齿轮中任一超过缺陷阈值即为“不合格”。默认阈值来自
`model/model2/inference_config.json`。辅助划痕框只用于复核，不单独决定结果。

合格发送 ASCII `01`，不合格发送 ASCII `02`。未定位到齿轮不计数、不发送串口；默认
5 秒冷却时间避免连续帧重复计数。视频测试模式始终禁用串口。

## 4. 状态、配置与权限

API 状态由运行时生成，包含任务、数据源、统计、最新结果、设置、控制锁，以及相机、模型
和串口健康信息。WebSocket 每 0.5 秒推送一次完整快照，HTTP 状态接口用于首次加载和诊断。

运行设置写入 `var/settings.json`，采用临时文件加原子替换。密码、会话、模型路径和上传
临时文件不进入设置文件或 Git。启动配置顺序为：

```text
代码与模型默认值 → var/settings.json → GEARPRO_* 环境变量
```

共享密码建立最长 8 小时的 HttpOnly 会话。一个会话可以取得 30 秒操作员租约，页面每
10 秒续期；其他会话保持只读。所有更改设备状态的 API 都同时检查登录会话和控制租约。

## 5. 部署边界

- 生产部署直接提供 `gp/static/`，Jetson 不需要 Node 或桌面环境。
- 默认监听 `0.0.0.0:8000`，必须配置 `GEARPRO_WEB_PASSWORD`。
- 内置 HTTP 只面向可信隔离局域网；跨网段或公网必须使用 HTTPS 反向代理。
- 目前只有单相机、单流水线和内存统计，不包含数据库、用户分级或云端模型管理。
- 模型性能、阈值、照明、显存和串口闭环必须在目标 Jetson 与产线设备上标定。
