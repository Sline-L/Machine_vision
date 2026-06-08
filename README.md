# Machine Vision YOLO Detection System

基于 PyQt5、OpenCV 和 Ultralytics YOLO 的实时机器视觉检测原型项目。当前程序从工业相机/USB 摄像头读取画面，使用 YOLO 模型识别零件状态，并通过串口向外部设备发送检测结果。

## 功能概览

- 实时摄像头采集与原始画面显示
- YOLO 目标检测线程
- 检测类别、置信度和统计信息显示
- 检测结果串口输出
- 模型导出脚本示例
- 多模式 UI 原型，包括自由模式、定量模式、定时模式、拍摄模式和校准界面

## 项目结构

```text
.
├── gp_main.py                    # 当前主程序入口
├── gp_mainwindow.py              # 主窗口和整体 UI 布局
├── gp_cameradisplaywidget.py     # 摄像头读取与原始画面显示
├── gp_detectiondisplaywidget.py  # 检测结果面板、按钮和串口触发逻辑
├── gp_detectionworker.py         # YOLO 检测工作线程
├── gp_globals.py                 # 全局帧缓存、锁、模型和运行状态
├── gp_serial.py                  # 串口连接与发送封装
├── aicode.py                     # 多模式 UI 原型
├── new1                          # 早期单文件版实时检测程序
├── zhuanhua.py                   # PyTorch 模型导出 ONNX 示例
├── seria1l.py                    # 串口发送测试脚本
├── best.pt / newb.pt             # YOLO PyTorch 权重文件
├── best.onnx                     # ONNX 模型文件
├── gear.dlc                      # 设备端模型文件
└── ultralytics/                  # 本地 Ultralytics 源码，版本 8.4.13
```

## 运行环境

当前代码主要面向 Linux 环境，摄像头使用 OpenCV V4L2 后端，Qt 默认设置为 X11：

```python
os.environ["QT_QPA_PLATFORM"] = "xcb"
```

建议环境：

- Python 3.10+
- Linux 桌面环境或支持 X11 的运行环境
- 可用摄像头设备
- 如需串口输出，需要可用串口设备，当前默认端口为 `/dev/ttyHS1`

## 安装依赖

建议创建虚拟环境：

```bash
python -m venv .venv
source .venv/bin/activate
```

安装常用依赖：

```bash
pip install PyQt5 opencv-python pyserial numpy torch torchvision
```

本项目已包含本地 `ultralytics/` 源码，程序会优先使用项目目录中的 Ultralytics 包。

## 启动程序

```bash
python gp_main.py
```

程序启动后会打开实时检测窗口：

- 左侧显示摄像头原始画面
- 右侧点击“开始检测”启动 YOLO 检测
- 检测到 `good` 时发送串口数据 `01`
- 检测到 `miss` 时发送串口数据 `02`

## 重要配置

当前项目仍处于原型阶段，部分参数写在代码中：

- 摄像头索引：`gp_mainwindow.py` 中默认使用 `CameraDisplayWidget(2)`
- 串口端口：`gp_serial.py` 中默认使用 `/dev/ttyHS1`
- 串口波特率：`9600`
- 检测置信度：`gp_detectionworker.py` 中默认 `conf=0.7`
- 模型路径：`gp_globals.py` 中目前是绝对路径

在不同电脑上运行前，建议先检查并修改这些配置。

## 模型文件说明

仓库根目录包含多个模型文件：

- `best.pt`：PyTorch YOLO 权重
- `newb.pt`：另一个 PyTorch YOLO 权重
- `best.onnx`：ONNX 导出模型
- `gear.dlc`：面向设备端部署的模型格式

如果模型文件较大，建议使用 Git LFS 管理，避免普通 Git 仓库体积过大。

## 导出 ONNX

`zhuanhua.py` 展示了使用 Ultralytics 导出 ONNX 的基本方式：

```bash
python zhuanhua.py
```

运行前需要确认脚本中的模型路径指向实际存在的 `.pt` 文件。

## 串口测试

可以使用以下脚本单独测试串口发送：

```bash
python seria1l.py
```

当前默认向 `/dev/ttyHS1` 发送字符串 `01`。

## 当前已知问题

- `gp_globals.py` 中模型路径为本机绝对路径，迁移到其他机器时需要改为相对路径或配置文件。
- 检测频率按钮目前修改了 UI 状态，但检测线程实际仍固定 `time.sleep(0.1)`。
- `new1` 和 `aicode.py` 属于原型/历史脚本，后续应整合或移入实验目录。
- 当前缺少统一依赖文件，例如 `requirements.txt`。
- 当前缺少自动化测试。
- 本地包含完整 `ultralytics/` 源码，发布前需要确认许可证和分发方式。

## 后续重构方向

- 统一命名为 `gearpro_*` 或整理为标准 Python 包结构
- 将模型路径、摄像头索引、串口端口、置信度阈值移动到配置文件
- 将全局变量封装为应用状态或服务对象
- 用 `QThread` 替代裸 `threading.Thread`，更贴合 PyQt 生命周期
- 增加计数统计：总数、合格数、不合格数
- 整合设置界面、检测界面和图表显示
- 增加 `requirements.txt`、`.gitignore` 和基础测试

## License

当前项目尚未声明许可证。发布到 GitHub 前请根据实际用途选择合适许可证，并注意 Ultralytics 相关代码的许可证要求。
