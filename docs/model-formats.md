# 模型格式：`.pt`、`.onnx`、`.engine`

本文记录 GearPro 在 Jetson NX 上的权重格式选择。三种格式不是互相替代的
“升级关系”，而是开发、交换和上板加速三条线。

当前仓库默认仍使用 `.pt`。应用层（相机、UI、串口、计数）不依赖具体格式；
真正绑定推理后端的只有 `gp/models.py`。

## 1. 各自是什么

| 格式 | 本质 | 运行时 |
| --- | --- | --- |
| `.pt` | PyTorch 权重或 checkpoint | PyTorch + CUDA |
| `.onnx` | 计算图中间交换格式 | ONNX Runtime、TensorRT 等 |
| `.engine` | TensorRT 针对**当前 GPU 与 TensorRT 版本**编好的执行计划 | TensorRT Runtime |

常见流水线是 `.pt → .onnx → .engine`。`.engine` 不是 ONNX 的更高版本，而是
某一台机器上的编译产物。

## 2. 对比

| | `.pt` | `.onnx` | `.engine` |
| --- | --- | --- | --- |
| NX 吞吐 | 基线，适合第一次上板 | 中等，取决于执行提供器 | 通常最快，尤其 FP16 |
| 与训练一致性 | 最高 | 高，便于和 `.pt` 对数值 | FP16 一般可接受；INT8 必须回归 |
| 换电脑能否直接用 | 能 | 能 | 不能，必须在目标板重编 |
| 改模型 / 调参 | 最容易 | 需重导出 | 每次改图都要重编译 |
| 工程复杂度 | 当前代码已支持 | 需固定 opset、输入尺寸、NMS 是否进图 | 还依赖 JetPack / TensorRT 版本 |
| 适合阶段 | 开发、精度对照、第一次 NX 测试 | 跨框架交换、转 TRT 的桥 | 节拍不够时的产线加速 |

`.engine` 与 Jetson 架构、JetPack、TensorRT 大版本绑定。不要在 Windows 或
另一块板上预先编译 NX 使用的 engine。

## 3. 和两阶段流水线的关系

不要两个模型一刀切。

- **定位 YOLO（`model1`）**：结构更深、通常占时更多。开发期继续 `.pt`；
  上板冲节拍时优先转 TensorRT。Ultralytics 对 `.pt` / `.onnx` / `.engine`
  均可 `YOLO(path).predict()`，应用层改动很小。
- **分类 ResNet18（`model2`）**：体积已经较小，只对裁剪后的 ROI 推理。
  若 YOLO 已是瓶颈，分类器可以继续 `.pt` 或停在 ONNX。分类预处理
  （BGR→RGB、缩放到 checkpoint 中的尺寸、ImageNet mean/std）应留在
  Python 侧，以便和训练对齐。

微小划痕对量化敏感。顺序固定为：先用 `.pt` 建立延迟与精度基线，再导出
ONNX 做数值对照，然后在 **NX 本机** 编 FP16 engine。只有 FP16 精度仍可接受
且速度仍不够时，才评估带校准集的 INT8。

## 4. 上板步骤

1. 在 NX 上直接跑当前 `.pt`，记录单帧延迟、显存和与 PC 判定是否一致。
2. 导出 ONNX，用同一批图对比框坐标和缺陷概率。
3. 在 NX 本机将 ONNX（或 Ultralytics `format=engine`）编成 `.engine`。
4. 用环境变量切换路径，不必改业务代码：

```bash
GEARPRO_MODEL1=/path/to/model1.engine \
GEARPRO_MODEL2=/path/to/model2.pt \
python gp_main.py
```

YOLO 换成 `.onnx` / `.engine` 后，Ultralytics 仍可能直接加载；分类器若仍是
`.pt`，继续走现有 ResNet18 路径。分类器要上 ONNX/TensorRT 时，只需扩展
`gp/models.py` 的加载与前向，不必改 UI 或串口。

旧版 YOLO 导出示例见 `legacy/zhuanhua.py`，仅作参考。新版导出应固定
`imgsz`、batch=1，并确认 NMS 是否包含在图内，避免后处理与训练时不一致。

## 5. 仓库中的资产约定

- `.pt` 和经过验证的 `.onnx` 可作为可搬运资产保留。
- `.engine` 视为构建产物：换板或升级 JetPack 后必须重编，不要把它当成
  跨机器分发的“最终模型”。
- 当前默认文件仍是 `model/model1.pt` 与 `model/model2.pt`。
  `model/model_old.pt` 是替换分类器之前的旧权重，只用于对照。
