# GearPro 齿轮视觉检测系统

GearPro 是运行在 Jetson 或 Linux 工控机上的齿轮在线视觉检测系统。当前 `main-web`
版本使用 FastAPI 提供后端服务、Vue 3 提供局域网浏览器界面，不再依赖 Qt 桌面环境。
模型首先定位齿轮，再通过 Scratch V5 三模型融合判断划痕，并把结果显示、统计和发送给
外部串口设备。

## 主要功能

- 浏览器实时查看相机原图或标注结果，默认最高 10 FPS。
- Model1 齿轮定位与 Scratch V5 两阶段推理。
- 显示融合概率、分类概率、检测概率及各阶段耗时。
- 自由、定量、定时和视频测试模式。
- 浏览器上传测试视频，测试期间自动禁用串口。
- 多终端同时查看、单操作员控制锁和共享密码登录。
- 运行参数跨重启保存，密码和模型路径不写入本地设置。
- 合格发送 ASCII `01`，不合格发送 ASCII `02`。

## 检测流程

```text
相机或测试视频
  └─ model/model1.pt：YOLO 定位 gear
       └─ 裁剪高分辨率齿轮 ROI
            └─ model/model2/：Scratch V5
                 ├─ EfficientNet-B0 分类器
                 ├─ ResNet18 分类器
                 ├─ YOLO26-P2 划痕检测器
                 └─ 0.25 × 分类均值 + 0.75 × 检测概率
                      ├─ Web 实时显示与统计
                      └─ 串口输出 01 / 02
```

## 项目结构

```text
.
├── gp_main.py             # 直接启动入口
├── gp/                    # Python 后端、运行时及构建后的前端
│   ├── app.py             # CLI 与 Uvicorn 启动
│   ├── web.py             # FastAPI、WebSocket 和视频流 API
│   ├── runtime.py         # 相机、推理、统计和串口生命周期
│   ├── camera.py          # 无界面的 OpenCV 相机线程
│   ├── worker.py          # 常驻推理线程
│   ├── models.py          # 两阶段推理流水线
│   ├── scratch_v5.py      # Model2 融合运行时
│   └── static/            # 已构建的 Web 页面，可直接部署
├── web/                   # Vue 3/Vite 前端源代码
├── model/                 # Model1 与 Scratch V5 模型包
├── docs/                  # 架构、API 和模型文档
├── tests/                 # 无硬件测试
├── legacy/                # 历史程序和资产
└── ultralytics/           # 项目内置 Ultralytics
```

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

生产端使用已构建的 `gp/static/`，不需要安装 Node。只有修改前端时才需要：

```bash
cd web
npm install
npm run build
```

## 启动与访问

局域网运行必须设置共享密码：

```bash
source .venv/bin/activate
export GEARPRO_WEB_PASSWORD='请替换为现场密码'
python gp_main.py
```

也可以使用：

```bash
python -m gp --host 0.0.0.0 --port 8000
```

终端会显示服务地址。在同一局域网的电脑或平板访问 `http://<Jetson-IP>:8000`。

仅本机开发可免密码：

```bash
python gp_main.py --host 127.0.0.1
```

服务器已有视频时仍可从命令行进入测试模式：

```bash
python gp_main.py --host 127.0.0.1 --video /path/to/test.mp4
```

不接摄像头、用磁盘图片走完整推理（真实 locator / Scratch V5 / GPU；不要用锁定的 `test_scratch` 调阈值）：

```bash
python gp_main.py --host 127.0.0.1 --replay /path/to/non_locked_frames
```

网页中也可上传 `mp4/avi/mov/mkv/m4v`。默认上传上限为 2048 MB；测试视频保存在
Git 忽略的 `var/uploads/`，切换视频、返回相机或关闭服务时自动清理。

## Web 操作规则

登录后的终端都可查看画面和状态，但只有一个终端能“接管控制”。控制租约每 10 秒续期，
30 秒未收到心跳后自动释放。只有控制终端可以启停检测、上传视频、切换相机、清空统计
和修改设置。浏览器关闭不会停止正在运行的检测任务。

网页设置写入 `var/settings.json`。配置优先级为代码默认值、本地设置、部署环境变量。
模型路径、访问密码只通过部署环境配置。

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `GEARPRO_WEB_HOST` | `0.0.0.0` | Web 监听地址 |
| `GEARPRO_WEB_PORT` | `8000` | Web 端口 |
| `GEARPRO_WEB_PASSWORD` | 无 | 局域网访问密码；非回环监听时必填 |
| `GEARPRO_MAX_UPLOAD_MB` | `2048` | 浏览器视频上传上限 |
| `GEARPRO_CAMERA_INDEX` | `2` | 摄像头索引 |
| `GEARPRO_SERIAL_PORT` | `/dev/ttyHS1` | 串口设备 |
| `GEARPRO_MODEL1` | `model/model1.pt` | 齿轮定位模型 |
| `GEARPRO_MODEL2` | `model/model2/inference_config.json` | Scratch V5 配置 |
| `GEARPRO_REPLAY_DIR` | 无 | 数据集回放目录（与 `--replay` 相同；关闭串口） |

内置服务使用 HTTP，适用于可信且隔离的生产局域网。跨网段或公网访问必须放在 HTTPS
反向代理后，并增加相应的网络访问控制。

## 验证

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
python -m py_compile gp_main.py gp/*.py legacy/*.py
python -m pip check
cd web && npm run build
```

真实相机、CUDA、串口和局域网多终端仍需在目标 Jetson NX 上完成硬件联调。

## 文档

- [文档索引](docs/README.md)
- [系统架构](docs/architecture.md)
- [Web API](docs/web-api.md)
- [Scratch V5](docs/scratch-v5.md)
- [模型产物契约](docs/model-bundle.md)
- [模型格式与 Jetson 部署](docs/model-formats.md)

当前 Scratch V5 只识别划痕，独立测试 Recall 为 `0.8065`，仍是可运行基线而不是已经
达到生产目标的最终模型。

## License

项目许可证见 [LICENSE.md](LICENSE.md)。对外发布前还需确认内置 `ultralytics/` 源码
和模型文件的许可证兼容性。
