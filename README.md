# GearPro 齿轮视觉检测系统

GearPro 是基于 PyQt5、OpenCV 和 PyTorch 的齿轮在线视觉检测程序。新版使用两个模型
串联推理：先定位齿轮，再对高分辨率齿轮 ROI 做缺陷分类，以减少直接缩放整张相机图像
造成的微小缺陷信息损失。

## 主要功能

- 工业相机/USB 摄像头实时画面
- `model1.pt` 定位齿轮，`model2.pt` 判定缺陷
- 推理线程与 UI 解耦，始终处理最新画面
- 已检测、合格、不合格计数及柱状统计图
- 自由、定量、定时三种运行模式
- 定位阈值、缺陷阈值、推理间隔和摄像头设置
- 合格发送串口代码 `01`，不合格发送 `02`
- 旧版代码完整归档并可独立启动

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python gearpro_main.py
```

默认使用摄像头索引 `2`、串口 `/dev/ttyHS1` 和波特率 `9600`。这些硬件默认值与旧版
一致。模型默认读取：

- `model/model1.pt`：YOLO 齿轮定位模型
- `model/model2.pt`：ResNet18 缺陷分类模型

## 项目结构

```text
.
├── gearpro_main.py           # 新版入口
├── gearpro_config.py         # 配置与项目路径
├── gearpro_camera.py         # 相机和最新帧缓冲
├── gearpro_models.py         # 两阶段推理
├── gearpro_worker.py         # 后台推理线程
├── gearpro_serial.py         # 串口输出
├── gearpro_types.py          # 结果与统计对象
├── gearpro_ui.py             # 主界面和设置界面
├── model/                    # 新版模型
├── legacy/                   # 重构前代码和实验脚本
├── docs/                     # 方案与架构文档
├── tests/                    # 不依赖硬件的核心测试
└── ultralytics/              # 项目内置 Ultralytics 源码
```

旧版主程序运行方式：

```bash
python legacy/gp_main.py
```

两阶段推理细节、环境变量配置、模型预处理假设及当前硬件边界见
[`docs/新版架构与运行说明.md`](docs/新版架构与运行说明.md)。

## 验证

```bash
python -m unittest discover -s tests -v
python -m py_compile gearpro_*.py legacy/*.py
```

真实推理和串口输出需要在安装完整依赖并连接摄像头/串口的目标设备上验证。

## License

项目许可证见 [LICENSE.md](LICENSE.md)。发布或分发项目前，还需确认内置
`ultralytics/` 源码及所用模型对应许可证的兼容性。
