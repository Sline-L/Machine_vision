# Scratch V5 迁移与集成说明

## 1. 文档目的

本文档说明 Scratch V5 的用途、模型结构、数据格式、训练过程、推理协议、测试结果和迁移要求，供主项目集成时使用。

Scratch V5 只回答一个问题：**当前齿轮图片中是否存在划痕**。

- `PASS`：模型认为图片中没有划痕。
- `REJECT`：模型认为图片中存在划痕。
- 不区分划痕种类。
- 不要求检测框位置精确。
- 检测框仅作为人工复核的辅助信息，不能单独决定 PASS/REJECT。
- 生产目标是漏检优先，同时限制正常齿轮误剔除率。

当前版本标识为 `scratch_v5`，随机种子为 `20260911`。

## 2. 当前状态

V5 已完成数据准备、候选训练、融合选择、验证集评估和一次锁定的独立测试集评估。

### 2.1 验证集结果

验证集参与了模型选择、温度校准、融合方式选择和阈值选择，因此这些结果不能视为严格盲测结果。

| 指标 | 结果 |
| --- | ---: |
| 图片数 | 150 |
| 划痕 / 正常 | 43 / 107 |
| Recall | 0.9767 |
| Precision | 0.8235 |
| F1 | 0.8936 |
| 正常误报率 FPR | 0.0841 |
| AUROC | 0.9715 |
| AUPRC | 0.9366 |
| TP / FP / TN / FN | 42 / 9 / 98 / 1 |

### 2.2 独立测试集结果

`test_scratch` 在模型、融合规则和默认阈值锁定后只评估了一次，没有用来重新选择阈值。

| 指标 | 结果 |
| --- | ---: |
| 图片数 | 150 |
| 划痕 / 正常 | 31 / 119 |
| 划痕框 | 72 |
| Recall | 0.8065 |
| Precision | 0.5556 |
| F1 | 0.6579 |
| 正常误报率 FPR | 0.1681 |
| Specificity | 0.8319 |
| NPV | 0.9429 |
| AUROC | 0.8832 |
| AUPRC | 0.8125 |
| TP / FP / TN / FN | 25 / 20 / 99 / 6 |

结论：独立测试集上的正常误报率仍低于 20%，但 Recall 没有达到 95% 目标。主项目集成时应把 V5 视为可运行基线，而不是已经完全达到生产要求的最终模型。

验证集预先保存的激进阈值 `0.203814` 在独立测试集上可获得 0.9355 Recall，但 FPR 会升至 0.5882，不建议作为默认生产阈值。

## 3. 最终模型组成

最终判定由两个整图分类器和一个辅助检测器融合得到。

| 文件 | 模型 | 输入 | 温度 | 大小 | SHA256 |
| --- | --- | ---: | ---: | ---: | --- |
| `classifier_1.pt` | EfficientNet-B0 二分类 | 384×384 | 0.7 | 16,314,725 B | `44461F4E03FF716266A3123BF1BA4611A1C965CF8776D0E523F128CF7C0B8438` |
| `classifier_2.pt` | ResNet18 二分类 | 384×384 | 2.05 | 44,780,619 B | `D07678A6DA421C4EDC00AC24B8C5052B0B8B7F8B1614B9D82563ECEFBF59360D` |
| `detector.pt` | YOLO26-P2 单类检测 | 960×960 | 2.125 | 5,902,651 B | `4451E3F3664E3AD551926DC771E8CF4D0DA9CD6648A9B841EA9D22BEA86F15B3` |

权重目录：

```text
outputs/scratch_v5/final/
├─ classifier_1.pt
├─ classifier_2.pt
└─ detector.pt
```

注意：

- `classifier_1.pt` 和 `classifier_2.pt` 是本项目自定义的 PyTorch checkpoint，不是 Ultralytics 分类模型，不能直接用 `YOLO(path)` 加载。
- `detector.pt` 是 Ultralytics YOLO 权重，可通过 `YOLO(path)` 加载。
- PyTorch checkpoint 使用 pickle 机制，只能加载可信来源的权重。

## 4. 推理算法

### 4.1 分类器预处理

每张图片按以下顺序处理：

1. 使用 Pillow 读取并转换为 RGB。
2. 保持宽高比，将最长边缩放至 384。
3. 在 384×384 画布上居中填充，填充值为 RGB `(238, 238, 238)`。
4. 转换为 Tensor。
5. 使用 ImageNet 参数标准化：

```text
mean = (0.485, 0.456, 0.406)
std  = (0.229, 0.224, 0.225)
```

当前最终配置未启用 TTA，`tta` 为 `none`。

### 4.2 检测器预处理

检测器由 Ultralytics 执行标准 letterbox 预处理：

- 输入尺寸：960。
- 原始置信度下限：0.001。
- NMS IoU：0.7。
- 图像级检测概率取所有预测框中的最高置信度。
- 对外只显示最高置信度的一个辅助框，避免大量重叠框影响人工复核。

### 4.3 温度校准

三个模型的原始概率分别按验证集选出的温度进行校准：

```text
calibrated(p, T) = sigmoid(logit(clamp(p, 1e-6, 1-1e-6)) / T)
```

不要在迁移时删除温度校准，否则最终概率分布和阈值含义会改变。

### 4.4 融合规则

设：

- `c1` 为 EfficientNet-B0 校准后的划痕概率。
- `c2` 为 ResNet18 校准后的划痕概率。
- `d` 为 YOLO26-P2 最高框置信度校准后的概率。

融合过程：

```text
classifier_probability = (c1 + c2) / 2
scratch_probability = 0.25 * classifier_probability + 0.75 * d
```

默认判定：

```text
scratch_probability >= 0.300273610279458  -> REJECT
scratch_probability <  0.300273610279458  -> PASS
```

这里的 `alpha=0.25` 是分类器均值的权重，检测器权重为 `1-alpha=0.75`。

## 5. 推理输入输出

### 5.1 支持的输入

推理入口支持单张图片或目录递归扫描，支持扩展名：

```text
.jpg .jpeg .png .bmp .tif .tiff .webp
```

输入应尽量满足：

- 一张图片只有一颗主要齿轮。
- 齿轮没有被画面边缘严重裁切。
- 拍摄距离、曝光、背景和训练数据大致相近。
- OpenCV/Pillow 能正常解码。

### 5.2 命令行接口

```powershell
& ".venv\Scripts\python.exe" "infer_scratch_v5.py" `
  "待检测图片或目录" `
  --config "outputs\scratch_v5\inference_config.json" `
  --output "outputs\scratch_v5\inference" `
  --device 0
```

可选参数：

| 参数 | 含义 | 默认值 |
| --- | --- | --- |
| `source` | 单张图片或图片目录 | 必填 |
| `--config` | 推理配置 JSON | `outputs/scratch_v5/inference_config.json` |
| `--output` | CSV 和可视化目录 | `outputs/scratch_v5/inference` |
| `--threshold` | 临时覆盖默认阈值 | 配置中的默认阈值 |
| `--device` | CUDA 卡号或 `cpu` | `0` |
| `--no-boxes` | 不绘制辅助检测框 | 关闭 |

### 5.3 CSV 输出

`predictions.csv` 每张图片一行：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `image` | string | 输入图片路径 |
| `decision` | `PASS` / `REJECT` | 最终判定 |
| `scratch_probability` | float | 最终融合概率 |
| `classifier_probability` | float | 两个分类器校准概率的平均值 |
| `detector_probability` | float | 检测器最高置信度的校准值 |
| `threshold` | float | 本次使用的阈值 |
| `visualization` | string | 可视化结果路径 |

主项目应以 `decision` 或 `scratch_probability >= threshold` 作为最终业务判断。`classifier_probability`、`detector_probability` 和检测框只用于日志、解释和复核。

### 5.4 推荐的主项目返回结构

主项目封装服务时建议返回：

```json
{
  "model_version": "scratch_v5",
  "decision": "REJECT",
  "scratch_probability": 0.7392,
  "threshold": 0.300273610279458,
  "classifier_probability": 0.9563,
  "detector_probability": 0.6668,
  "auxiliary_box": [43.0, 55.0, 158.0, 151.0],
  "latency_ms": 0.0
}
```

`latency_ms` 由主项目实际计时填写。若不需要人工复核，可省略 `auxiliary_box`，但不要省略检测器本身，因为检测器参与最终融合。

## 6. 配置文件说明

最终配置位于 `outputs/scratch_v5/inference_config.json`。

关键字段：

| 字段 | 说明 |
| --- | --- |
| `version` | 模型组合版本 |
| `classes` | 图像级业务类别，0 为 normal，1 为 scratch |
| `classifiers` | 分类器名称、架构、权重、输入尺寸、TTA、温度 |
| `detector` | 检测器权重、输入尺寸、温度、置信度下限和 NMS 参数 |
| `fusion.type` | 当前为 `weighted` |
| `fusion.alpha` | 分类器分支权重，当前为 0.25 |
| `default_threshold` | 默认生产判定阈值 |
| `operating_points` | 在验证集上保存的不同误报约束工作点 |
| `decision` | 判定规则说明 |

当前配置中的权重路径已改为相对于配置文件目录的路径：

```json
{
  "weights": "final/classifier_1.pt"
}
```

`infer_scratch_v5.py` 会以配置文件所在目录解析相对路径：

```python
config_dir = config_path.resolve().parent
weight_path = Path(model_config["weights"])
if not weight_path.is_absolute():
    weight_path = config_dir / weight_path
```

复制模型包时应保持配置与 `final/` 的相对目录关系。主项目若实现独立运行时，也应使用相同的解析规则。

## 7. 迁移文件清单

### 7.1 最小可运行迁移

保持现有脚本结构时至少复制：

```text
infer_scratch_v5.py
train_scratch_v5.py
outputs/scratch_v5/inference_config.json
outputs/scratch_v5/final/classifier_1.pt
outputs/scratch_v5/final/classifier_2.pt
outputs/scratch_v5/final/detector.pt
```

必须同时复制 `train_scratch_v5.py`，因为当前推理脚本从中导入：

- `apply_temperature`
- `clahe`
- `load_custom`
- `square_image`

原样迁移虽然能工作，但会让生产推理模块依赖训练代码。

### 7.2 推荐的主项目结构

建议迁移时拆成：

```text
main_project/
├─ models/scratch_v5/
│  ├─ inference_config.json
│  ├─ classifier_1.pt
│  ├─ classifier_2.pt
│  └─ detector.pt
├─ src/inspection/scratch_v5_runtime.py
└─ tests/test_scratch_v5_runtime.py
```

`scratch_v5_runtime.py` 应只保留推理所需内容：

- EfficientNet-B0 和 ResNet18 构造与 checkpoint 加载。
- RGB、等比缩放、灰色填充和 ImageNet 标准化。
- 温度校准。
- YOLO26-P2 加载与最高框概率提取。
- 融合和 PASS/REJECT 判定。
- 配置相对路径解析。

不要把训练数据集、采样器、优化器、自动搜索和训练输出逻辑带入生产进程。

### 7.3 需要保留训练能力时

额外复制：

```text
prepare_scratch_v5.py
train_scratch_v5.py
evaluate_scratch_v5_test.py
analyze_scratch_v5_errors.py
yolo26n.pt
yolo26n-cls.pt
dataset_defects/images/{train_scratch,val_scratch,test_scratch}/
dataset_defects/annotations/{train_scratch,val_scratch,test_scratch}/
```

`runs/scratch_v5/` 主要用于断点续跑和追溯历史，不是生产推理必需。`outputs/scratch_v5/test_scratch/` 应作为评估档案保留。

## 8. Python 与依赖

本次训练和测试的实际环境：

| 组件 | 版本 |
| --- | --- |
| Python | 3.13.12 |
| PyTorch | 2.14.0+cu130 |
| torchvision | 0.29.0+cu130 |
| Ultralytics | 8.4.142 |
| NumPy | 2.5.2 |
| Pillow | 12.3.0 |
| OpenCV | 5.0.0 |
| GPU | NVIDIA GeForce RTX 4060 Laptop GPU 8GB |

运行时直接依赖：

```text
torch
torchvision
ultralytics
numpy
pillow
opencv-python
```

建议主项目先在与上述版本一致的环境完成一致性测试，再逐项升级。自定义 PyTorch checkpoint 对 PyTorch/torchvision 架构定义较敏感，版本变化后必须重新跑基准样本。

CPU 路径在代码中存在，但本轮正式测试使用 CUDA 0；CPU 性能和一致性没有作为交付验收项。

## 9. 数据与标注约定

### 9.1 原始目录

```text
dataset_defects/
├─ images/
│  ├─ train_scratch/
│  ├─ val_scratch/
│  └─ test_scratch/
└─ annotations/
   ├─ train_scratch/
   ├─ val_scratch/
   └─ test_scratch/
```

- 图片存在同名 XML：划痕正样本。
- 图片不存在同名 XML：正常负样本。
- XML 格式为 Pascal VOC。
- XML 中只允许 `scratch`。
- 每个连续受损区域一个紧框。

因此，“没有 XML 就是正常样本”是强假设。导入新数据前必须人工确认无 XML 图片确实没有划痕，不能把尚未标注的图片直接当正常样本。

### 9.2 训练数据统计

| 集合 | 总图 | 划痕图 | 正常图 |
| --- | ---: | ---: | ---: |
| train | 364 | 119 | 245 |
| val | 150 | 43 | 107 |
| 合计 | 514 | 162 | 352 |

共有 373 个合法划痕框。

### 9.3 数据准备输出

执行 `prepare_scratch_v5.py` 后生成：

```text
dataset_defects/scratch_v5/
├─ images/{train,val}/
├─ labels/{train,val}/
├─ classification/{train,val}/{normal,defect}/
├─ data.yaml
├─ scratch_manifest.csv
├─ cross_split_near_duplicates.csv
└─ preflight_report.json
```

YOLO 标签固定为：

```text
0 x_center y_center width height
```

坐标均归一化到 `[0,1]`。正常图片使用空 TXT 标签。

数据准备会校验图片/XML尺寸、类别、边界框范围、同名关系、SHA256 和 dHash。跨 train/val 的近重复会从派生训练集排除 train 侧样本，但不会修改原始图片。

## 10. 训练方案

### 10.1 候选模型

快速筛选分类候选：

- ResNet18，384，缺陷权重 1。
- ResNet18，512，缺陷权重 2。
- EfficientNet-B0，384，缺陷权重 1。
- EfficientNet-B0，512，缺陷权重 2。
- YOLO26n-cls，384，缺陷权重 1。
- YOLO26n-cls，512，缺陷权重 2。

检测候选：

- 标准 YOLO26n，960。
- YOLO26-P2，960。

快速候选训练 30 至 35 轮；排名靠前的两个分类器最多精训 100 轮并早停。训练以验证集 FPR 不超过 20% 时的 Recall 为主要排序依据。

### 10.2 自定义分类器训练

- ImageNet 官方预训练权重初始化。
- AdamW，初始学习率 `3e-4`，weight decay `5e-4`。
- CosineAnnealingLR，最低学习率 `1e-6`。
- Focal BCE，gamma `1.5`。
- 按 `normal/scratch × face/oblique/side` 使用 WeightedRandomSampler。
- AMP 半精度训练。
- 384 输入 batch 24，512 输入 batch 12。
- hard-case：漏检划痕最多 3 倍，误报正常图最多 2 倍。

### 10.3 增强

训练集可能使用：

- 水平/垂直翻转。
- 90/270 度旋转。
- 轻量亮度和对比度。
- CLAHE。
- 高斯模糊。
- 高斯噪声。
- Gamma。
- JPEG 压缩。

未使用可能裁掉缺陷的随机裁剪、MixUp 和 CutMix。检测器关闭 Mosaic。

### 10.4 GPU 与 worker

- 单张 RTX 4060 串行训练候选，避免显存竞争。
- CUDA 0、AMP、RAM cache。
- 自定义分类器最多 8 workers。
- Ultralytics 检测器在 Windows 下固定最多 4 workers，避免 `OSError(22)`。
- OOM 时自动逐级减小 batch。

## 11. 复现命令

### 11.1 准备数据

```powershell
& ".venv\Scripts\python.exe" "prepare_scratch_v5.py"
```

重新生成派生目录：

```powershell
& ".venv\Scripts\python.exe" "prepare_scratch_v5.py" --force
```

`--force` 只应在确认要替换 `dataset_defects/scratch_v5` 派生目录时使用。

### 11.2 训练

```powershell
& ".venv\Scripts\python.exe" "train_scratch_v5.py" --hours 6 --workers 4
```

预检模型构造但不训练：

```powershell
& ".venv\Scripts\python.exe" "train_scratch_v5.py" --dry-run --workers 4
```

只复用已完成候选并重建排行榜、融合配置和报告：

```powershell
& ".venv\Scripts\python.exe" "train_scratch_v5.py" --hours 1 --workers 4 --finalize-only
```

### 11.3 独立测试

```powershell
& ".venv\Scripts\python.exe" "evaluate_scratch_v5_test.py"
```

评估器检测到已有 `test_report.json` 时默认拒绝覆盖，避免无意中反复使用锁定测试集。`--force` 只用于明确修复评估程序或更正测试数据的情况，不能用于反复选择模型。

## 12. 主项目集成建议

### 12.1 生命周期

生产服务启动时一次性加载三个模型，后续请求重复使用实例。不要每处理一张图片就重新执行脚本或重新加载权重。

推荐流程：

1. 服务启动时读取并校验配置。
2. 校验三个权重的 SHA256。
3. 加载两个分类器和一个检测器到同一 CUDA 设备。
4. 预热一张 384 和一张 960 的虚拟输入。
5. 请求到达后完成预处理、三分支推理、校准、融合和判定。
6. 记录版本、概率、阈值、耗时和最终决策。

### 12.2 并发

单 GPU 环境建议使用一个模型服务进程和有界请求队列。不要启动多个训练或推理进程争抢同一张 8GB GPU。

若需要批量处理，优先在同一进程中按批次推理。当前命令行实现会复用一次加载的模型处理整个目录，但自定义分类器内部仍逐图构造 batch，迁移到主项目时可进一步改造成真正的批量 Tensor 推理。

### 12.3 异常处理

以下情况建议返回明确错误或转人工复核，不要自动判为 PASS：

- 图片无法解码。
- 图片为空或尺寸异常。
- 配置/权重缺失或哈希不匹配。
- CUDA OOM。
- 任一模型输出 NaN/Inf。
- 齿轮不存在、严重遮挡或主体被裁切。

主项目可增加 `UNKNOWN` 或 `REVIEW` 状态承接上述情况。V5 原始 CLI 只有 PASS/REJECT，没有该状态。

### 12.4 日志字段

至少记录：

```text
request_id
timestamp
model_version
input_shape
scratch_probability
classifier_probability
detector_probability
threshold
decision
latency_ms
error_code
```

不要默认长期保存全部生产图片；图片留存策略应遵循主项目的数据和隐私要求。建议只保留经授权的低置信样本、漏检确认样本和误报确认样本用于后续迭代。

## 13. 迁移验收

迁移完成后至少执行以下检查：

1. 三个权重 SHA256 与本文一致。
2. 配置中的权重路径在新环境可解析。
3. CUDA 和三个模型均成功加载。
4. 同一张基准图片在旧项目和主项目中的三个分支概率、融合概率和 decision 一致。
5. 允许浮点误差，但 `scratch_probability` 建议绝对差不超过 `1e-5`；若 CUDA、PyTorch或硬件版本不同，可放宽并重新建立基线。
6. 正常冒烟样本 `val_001.jpg` 应输出 PASS，历史融合概率约 0.0693。
7. 划痕冒烟样本 `val_017.jpg` 应输出 REJECT，历史融合概率约 0.7392。
8. 单图、目录、损坏图片、无图片目录、CPU参数和CUDA OOM路径均有测试。
9. 运行独立测试集只能用于迁移一致性确认，不能据此改阈值；若实现完全一致，结果应为 TP/FP/TN/FN = 25/20/99/6。

## 14. 已知限制

- 独立测试 Recall 只有 0.8065，尚未达到生产目标。
- 6 张漏检主要是小面积、低对比度的正视/斜视划痕。
- 20 张误报主要与侧齿高光和正常加工纹理有关。
- 当前模型没有“未识别到齿轮”或“不确定”状态。
- 当前推理入口会加载三个模型，吞吐与延迟高于单模型方案。
- 历史报告和排行榜仍保存原开发机绝对路径；最终推理配置已改为相对路径。
- 当前推理脚本依赖训练脚本，不适合作为最终生产模块边界。
- `test_scratch` 只有 31 张划痕图，测试 Recall 的统计区间仍较宽。
- dHash 在固定背景和相似齿轮轮廓场景下容易产生相似误报；本轮未发现 SHA256 完全重复。

## 15. 下一版本方向

V6 建议保持 `test_scratch` 锁定，并另建未来盲测集。优先验证：

1. 使用第一阶段模型裁切并归一化齿轮 ROI。
2. 增加 2×2/3×3 重叠局部块的多实例分类器，以 top-k 或 max 汇总局部概率。
3. 局部分支比较 RGB、CLAHE、高通或梯度表示。
4. 比较 ConvNeXt-Tiny、EfficientNetV2-S 与当前 EfficientNet-B0。
5. 增加视角路由，侧视单独建模或设置经验证集选择的工作点。
6. 新增无划痕侧齿高光和正常加工纹困难负样本，以及低对比度小划痕正样本。
7. 所有模型和阈值只在 train/val 上选择，锁定后再使用一套新的独立测试集。

详细错误样例与后续建议位于 `outputs/scratch_v5/test_scratch/OPTIMIZATION_NOTES.md`。

## 16. 迁移检查清单

- [ ] 复制并校验三份权重。
- [ ] 复制推理配置并修正权重路径。
- [ ] 将运行时代码与训练代码解耦。
- [ ] 固定 RGB、填充色、归一化、温度和融合公式。
- [ ] 服务启动时一次加载并预热模型。
- [ ] 增加 UNKNOWN/REVIEW 异常路径。
- [ ] 对照两张冒烟样本验证概率和判定。
- [ ] 保存模型版本和三分支概率日志。
- [ ] 保持 `test_scratch` 锁定。
- [ ] 为 V6 准备新的独立测试集。
