# 模型格式：`.pt` 与 `.engine`

GearPro 运行只使用这两种格式。`.pt` 是开发和精度基线；`.engine` 是在
**当前这块 Jetson NX** 上用 TensorRT 编出来的加速产物。

应用层（相机、UI、串口、计数）不绑格式。定位换成 engine 只改 Model1 路径；
Scratch V5 的三个分支继续用 `.pt`。

Ultralytics 编 engine 时会在中间写出 ONNX，那只是编译过程，不作为运行格式。
本机 ONNX Runtime 没有 CUDA，跑 ONNX 会比 `.pt` 更慢，因此不再提供 ONNX 启动入口。

## 1. 对比

| | `.pt` | `.engine` |
| --- | --- | --- |
| NX 吞吐 | 基线 | 通常更快（FP16） |
| 与训练一致性 | 最高 | FP16 一般可接受 |
| 换电脑 | 能直接用 | 不能，必须在目标板重编 |
| 适合阶段 | 开发、精度对照、改模型 | 板上加速 |

`.engine` 与 GPU、JetPack、TensorRT 版本绑定。不要在 Windows 上编了再拷到 NX。

## 2. 和两阶段流水线的关系

不要两个模型一刀切。

- **定位 YOLO（`model1`）**：占时更多，优先转 TensorRT。在 NX 运行
  `export_engine.py`，产物为 `model/model1/model1.engine`（须带 `manifest.json` SHA）。
  再用 `run_engine.py` 或 `TRT_FAST`。
- **融合模型（`model2`）**：EfficientNet-B0、ResNet18、YOLO26-P2 三份 `.pt`，
  由 `model/model2/inference_config.json` 描述。预处理留在 Python 侧。

顺序：先用 `.pt` 确认判定，再编 FP16 engine。INT8 最后做（划痕敏感）。

## 3. 上板

1. 右键 `run_pt.py`，确认划痕判定。
2. 右键 `export_engine.py`（只需在换 `model1.pt` 或升级 JetPack 后重做）。
3. 右键 `run_engine.py`。

也可以用环境变量：

```bash
GEARPRO_MODEL1=/path/to/model1.engine \
GEARPRO_MODEL2=/path/to/model2/inference_config.json \
python gp_main.py
```

Model2 任一分支以后若也转 engine，必须重新验证三路概率、温度校准和融合结果。

## 4. 资产约定

- `.pt` 可随仓库搬运：`model/model1.pt` 与 `model/model2/` 融合包。
- `.engine` 是板上 TensorRT 产物，**不提交**（`*.engine` gitignore），但必须放在稳定路径
  `model/model1/model1.engine`，并由 `model/model1/manifest.json` 记录 SHA256、源 `.pt` SHA
  和 TensorRT 版本。不要把正式 TRT_FAST 实验绑在匿名的 `.cache/exports/` 文件上。
- 重新导出后先更新 manifest SHA，再跑 TRT_FAST。
