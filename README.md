# GearPro 齿轮视觉检测系统

GearPro 是基于 PyQt5、OpenCV、PyTorch 和 Ultralytics 的齿轮在线视觉检测程序。系统
先从相机画面定位齿轮，再对高分辨率齿轮区域执行 Scratch V5 融合推理，降低整图缩放造成的微小缺陷
信息损失。

## 功能

- 实时工业相机或 USB 摄像头画面。
- YOLO 齿轮定位与 Scratch V5 三模型融合两阶段推理。
- 原图、划痕辅助框、融合概率、分支概率和推理耗时显示。
- 已检测、合格、不合格计数及柱状统计图。
- 自由、定量和定时三种运行模式。
- 可配置定位阈值、缺陷阈值、推理间隔、摄像头和串口。
- 合格发送串口代码 `01`，不合格发送 `02`。
- 推理线程与 UI 解耦，只处理最新相机帧。

## 检测流程

```text
摄像头画面
  └─ model/model1.pt：YOLO 定位 gear
       └─ 裁剪高分辨率齿轮 ROI
            └─ model/model2/inference_config.json：Scratch V5
                 ├─ EfficientNet-B0 + ResNet18 分类均值
                 ├─ YOLO26-P2 划痕检测概率
                 └─ 0.25 × 分类 + 0.75 × 检测
                 ├─ UI 显示与统计
                 └─ 串口输出 01 / 02
```

## 项目结构

```text
.
├── gp_main.py                # 直接启动入口
├── gp/                       # 新版应用包
│   ├── app.py                # Qt 初始化与应用启动
│   ├── camera.py             # 相机与最新帧缓冲
│   ├── config.py             # 路径及运行配置
│   ├── models.py             # 两阶段模型流水线
│   ├── scratch_v5.py         # Model2 配置、校准和融合运行时
│   ├── serial_io.py          # 串口输出
│   ├── types.py              # 结果与统计类型
│   ├── ui.py                 # 主界面与设置界面
│   └── worker.py             # 后台推理线程
├── model/                    # Model1 及 Scratch V5 Model2 模型包
├── docs/                     # 架构和优化文档
├── tests/                    # 无硬件单元测试
├── legacy/                   # 旧程序、模型和实验资料
├── ultralytics/              # 项目内置 Ultralytics 源码
└── requirements.txt
```

## 环境要求

- Linux；当前相机实现使用 OpenCV V4L2。
- Python 3.10 或更高版本。
- PyQt5、OpenCV、PyTorch、Torchvision、NumPy 和 PySerial。
- 运行检测需要摄像头；发送结果需要串口设备。

创建新环境：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

仓库本地已有环境时，只需激活：

```bash
source .venv/bin/activate
```

`.venv/` 是本机运行环境，不纳入 Git。

## 启动

在 NX 的 VS Code 里可右键下面的文件，选“在终端中运行 Python 文件”（需已选中
项目 `.venv` 解释器）。摄像头默认索引 `0`，可在设置里改。

| 文件 | 作用 |
| --- | --- |
| `run_pt.py` | 当前 `.pt` 基线 |
| `run_engine.py` | 定位用板上的 `model1.engine`，Model2 仍使用融合 `.pt` 包 |
| `run_onnx.py` | 定位用 ONNX（这台 NX 上是 CPU，只做对比） |

也可以命令行启动，两种方式等价：

```bash
python gp_main.py
```

```bash
python -m gp
```

测试视频可通过命令行直接传入，程序会自动进入视频测试模式并开始逐帧识别：

```bash
python gp_main.py --video /path/to/test.mp4
```

也可以在主界面点击“测试视频”选择文件。视频测试模式按原始帧率顺序处理每一帧，默认
禁用串口输出，防止离线测试误触发外部设备；识别结束后窗口保留最终结果，可点击
“实时相机”返回相机模式。

程序默认使用摄像头索引 `2`、串口 `/dev/ttyHS1` 和波特率 `9600`。可在界面右上角
“设置”中修改运行模式、阈值、推理间隔和硬件参数。

如果画面提示“摄像头打开失败”，先确认系统存在 `/dev/video*`，再按实际设备选择摄像头
索引。没有视频设备时程序仍可打开，但不会产生检测结果。

## 模型

| 文件 | 类型 | 作用 |
| --- | --- | --- |
| `model/model1.pt` | Ultralytics YOLO | 从完整相机画面定位 `gear` |
| `model/model2/inference_config.json` | Scratch V5 配置 | 解析三份权重、校准参数和融合阈值 |
| `model/model2/classifier_1.pt` | EfficientNet-B0 | 384×384 ROI 划痕分类 |
| `model/model2/classifier_2.pt` | ResNet18 | 384×384 ROI 划痕分类 |
| `model/model2/detector.pt` | YOLO26-P2 | 960×960 ROI 划痕检测与辅助框 |
| `model/model_old.pt` | ResNet18 二分类 | 旧分类器，仅作对照 |

两个分类器采用等比缩放、灰色居中填充和 ImageNet mean/std 归一化。三路概率经过温度
校准后融合，默认阈值为 `0.300273610279458`；界面仍统一显示为“缺陷概率”。V5 实际
只识别划痕，不覆盖缺齿等其他缺陷，详细说明见 [Scratch V5 运行说明](docs/scratch-v5.md)。

当前交付格式是 `.pt`。Jetson NX 上可按 `.pt` → `.onnx` → `.engine` 加速，不必先
改 UI 或串口；说明见 [模型格式](docs/model-formats.md)。

## 部署配置

Jetson NX 当前工作副本是 `/home/jetson/Projects/Machine_vision`（分支 `srtp`）。
重构前的旧树已归档到 `/home/jetson/archive/Machine_vision-old-2026-09-12`，不要在归档目录里继续改程序。

除界面设置外，可使用环境变量覆盖设备和模型路径：

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `GEARPRO_CAMERA_INDEX` | `2` | 摄像头索引 |
| `GEARPRO_SERIAL_PORT` | `/dev/ttyHS1` | 串口设备 |
| `GEARPRO_MODEL1` | `model/model1.pt` | 定位模型 |
| `GEARPRO_MODEL2` | `model/model2/inference_config.json` | Scratch V5 模型包配置 |

示例：

```bash
GEARPRO_CAMERA_INDEX=0 \
GEARPRO_SERIAL_PORT=/dev/ttyUSB0 \
python gp_main.py
```

## 验证

```bash
python -m unittest discover -s tests -v
python -m py_compile gp_main.py gp/*.py legacy/*.py
python -m pip check
```

无显示器环境可验证 Qt 启动：

```bash
QT_QPA_PLATFORM=offscreen python gp_main.py
```

## 文档与旧版

- [文档索引](docs/README.md)
- [系统架构](docs/architecture.md)
- [模型格式](docs/model-formats.md)
- [Scratch V5 运行说明](docs/scratch-v5.md)
- [模型优化路线](docs/optimization-roadmap.md)
- [旧版归档说明](legacy/README.md)

旧版主程序仍可从项目根目录运行：

```bash
python legacy/gp_main.py
```

旧版代码和模型与新版互相隔离。

## 当前限制

- 固定 5 秒冷却时间用于减少连续帧重复计数；正式产线建议由光电传感器触发。
- 视频测试按帧顺序执行，但零件计数仍沿用当前 5 秒防重复策略。
- 模型阈值和推理性能必须在目标 Jetson、工业相机及实际照明条件下标定。第一次
  上板继续使用 `.pt`；TensorRT engine 必须在 NX 本机编译。
- Scratch V5 独立测试 Recall 为 `0.8065`、正常误报率为 `0.1681`，当前是可运行
  基线，不是已经达到生产目标的最终模型。
- 当前没有摄像头或串口时仍可打开界面，但无法执行完整硬件闭环验证。

## License

项目许可证见 [LICENSE.md](LICENSE.md)。对外发布前还需确认内置 `ultralytics/` 源码
和模型文件的许可证兼容性。
