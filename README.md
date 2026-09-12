# 齿轮缺陷识别项目

本项目使用两阶段视觉流程：先检测并裁切整颗齿轮，再判断齿轮是否存在缺陷。历史上还训练过划痕和缺齿定位模型；当前主线 V4 是召回优先的 `normal/defect` 图像二分类。

## 当前状态

| 阶段 | 用途 | 当前推荐产物 |
| --- | --- | --- |
| 第一阶段 | 检测齿轮并裁切 ROI | `runs/gear_yolo26n_496train_50val_fixed/weights/best.pt` |
| 第二阶段 V4 | 判断有无任意缺陷 | `outputs/binary_defect_v4/final_ensemble/` 三模型融合 |
| 第二阶段 V3 | 区分并定位 scratch/missing_tooth | 保留用于研究和辅助复核，不建议直接生产剔除 |

V4 最终融合在当前留出集上的 Recall 为 0.633、Precision 为 0.731、正常误报率为 0.350，尚未达到 Recall 0.95 / FPR 0.30 的目标。重新训练时应优先增加独立拍摄的低对比划痕和强反光正常样本。

V5 只检测 `scratch`，同时使用两个图像分类器和一个单类检测器。当前验证集结果为 Recall 0.977、Precision 0.824、F1 0.894、正常误报率 0.084，已经达到 Recall >= 0.95 / FPR <= 0.20 的目标。验证集同时参与模型和阈值选择，因此该结果不是严格盲测成绩。

新增的 150 张 `test_scratch` 独立测试集固定阈值结果为 Recall 0.806、Precision 0.556、F1 0.658、正常误报率 0.168（TP/FP/TN/FN = 25/20/99/6）。完整结果位于 `outputs/scratch_v5/test_scratch/`；该测试集应继续锁定，不得用于后续训练和调阈值。

## 目录结构

```text
DATASET/
├─ README.md
├─ dataset_gear/                 第一阶段齿轮检测数据
├─ dataset_defects/              第二阶段缺陷原始数据和派生数据集
├─ runs/                         Ultralytics 与自定义模型训练目录
├─ outputs/                      最终权重、报告、预测和可视化
├─ weights/                      早期权重备份
├─ docs/                         当前项目文档
├─ archive/                      历史代码与旧说明
├─ .venv/                        Python 虚拟环境
├─ yolo26n.pt                    官方检测预训练权重
├─ yolo26n-cls.pt                官方分类预训练权重
├─ crop_dataset_defects.py       使用第一阶段模型裁切缺陷图片
├─ auto_optimize_defects_v3.py   V3 训练入口兼 V4 数据分组依赖
├─ infer_defects_v3.py           V3 推理入口
├─ train_binary_defect_v4.py     V4 二分类训练入口
├─ optimize_binary_defect_v4_ensemble.py
├─ infer_binary_defect_v4.py     V4 最终推理入口
├─ prepare_scratch_v5.py         V5 补图、VOC 转 YOLO 和数据预检
├─ train_scratch_v5.py           V5 分类/检测/融合自动训练
└─ infer_scratch_v5.py           V5 统一推理入口
```

`dataset_defects/`、`runs/` 和 `outputs/` 中包含很多历史实验副本。它们没有在本次代码归档中移动，以保证既有报告中的路径仍然有效。

## 当前代码

| 文件 | 作用 | 是否为当前主线 |
| --- | --- | --- |
| `crop_dataset_defects.py` | 用第一阶段齿轮模型识别并裁切 `dataset_defects/images/` | 是，数据预处理 |
| `train_binary_defect_v4.py` | 建立二分类拆分，训练 YOLO、ResNet、EfficientNet 和纹理候选 | 是 |
| `optimize_binary_defect_v4_ensemble.py` | 在验证集比较单模型与融合，并输出最终配置 | 是 |
| `infer_binary_defect_v4.py` | 对图片或目录输出 PASS/REJECT、缺陷概率和 CSV | 是 |
| `auto_optimize_defects_v3.py` | V3 完整训练；同时向 V4 提供 `Sample/load_samples/make_groups` | 依赖，暂不移动 |
| `infer_defects_v3.py` | V3 分类和定位推理 | 备选 |
| `prepare_scratch_v5.py` | 补齐 V5 原图、生成 YOLO 标签并检查跨集合近重复 | V5 |
| `train_scratch_v5.py` | 训练划痕分类器、检测器并搜索高召回融合方案 | V5 |
| `infer_scratch_v5.py` | 输出 PASS/REJECT、划痕概率和辅助框 | V5 |

## 数据约定

### 第一阶段

```text
dataset_gear/
├─ images/{train,val,test}/
├─ annotations/{train,val,test}/   Pascal VOC XML
├─ labels/{train,val,test}/        YOLO TXT
└─ data.yaml
```

### 第二阶段

```text
dataset_defects/
├─ images/{train,val,test}/
├─ annotations/{train,val,test}/
├─ gear_detection/                 自动裁切结果
├─ auto_search_v2/                 V2 派生数据，历史
├─ auto_search_v3/                 V3 派生数据
└─ binary_defect_v4/               V4 拆分和 YOLO 分类目录
```

V3/V4 当前从 `dataset_defects/images/train/` 和 `dataset_defects/annotations/train/` 读取 343 张可信样本。XML 中存在 scratch 或 missing_tooth 框时判为缺陷，没有框时判为 normal。

## 重新训练前

建议把下一轮命名为 V5，不要覆盖 V4。V4 已经用于多轮分析，其测试集不再是严格盲测。

1. 将新图片和对应 XML 放入新的版本化数据目录，或先完整备份现有 `dataset_defects`。
2. 按拍摄批次或连续视频段建立 group，同一组不得跨 train/val/test。
3. 检查每张图片只有一个确定的图像级标签：normal、scratch 或 missing_tooth。
4. 划痕按连续受损区域紧框；缺齿按独立损坏齿位分别框。
5. 测试集在拆分后立即锁定，不用于难例选择、阈值调整或模型选择。
6. 新实验使用新的 `dataset_defects/binary_defect_v5`、`runs/binary_defect_v5` 和 `outputs/binary_defect_v5`，保留 V4 作为历史基线。

注意：直接再次执行 `train_binary_defect_v4.py` 会复用现有拆分，并跳过带有 `complete.flag` 的已完成实验。它适合断点续跑，不适合作为一轮全新的盲测实验入口。

## Scratch V5

完整的模型结构、配置字段、依赖、推理公式、文件迁移清单和主项目集成要求见 [Scratch V5 迁移与集成说明](docs/Scratch_V5_迁移与集成说明.md)。

准备数据：

```powershell
& "F:\Work\VSCode\Projects\DATASET\.venv\Scripts\python.exe" `
  "F:\Work\VSCode\Projects\DATASET\prepare_scratch_v5.py"
```

约 6 小时自动训练：

```powershell
& "F:\Work\VSCode\Projects\DATASET\.venv\Scripts\python.exe" `
  "F:\Work\VSCode\Projects\DATASET\train_scratch_v5.py" `
  --hours 6 --workers 4
```

训练中断后可重复执行同一命令，已完成候选会自动复用。仅重新计算排行榜、融合阈值和最终输出时，追加 `--finalize-only`。

推理：

```powershell
& "F:\Work\VSCode\Projects\DATASET\.venv\Scripts\python.exe" `
  "F:\Work\VSCode\Projects\DATASET\infer_scratch_v5.py" `
  "图片或图片目录"
```

默认阈值满足验证集正常误报率不超过 20%。可通过 `--threshold` 手动切换敏感度；阈值越低，通常漏检越少、误报越多。

最终配置与详细结果位于 `outputs/scratch_v5/inference_config.json` 和 `outputs/scratch_v5/README.md`，生产推理应使用 `outputs/scratch_v5/final/` 下的三份权重。

## 当前 V4 复现

训练所有候选：

```powershell
& "F:\Work\VSCode\Projects\DATASET\.venv\Scripts\python.exe" `
  "F:\Work\VSCode\Projects\DATASET\train_binary_defect_v4.py" `
  --hours 6 --workers 4
```

训练完成后搜索融合：

```powershell
& "F:\Work\VSCode\Projects\DATASET\.venv\Scripts\python.exe" `
  "F:\Work\VSCode\Projects\DATASET\optimize_binary_defect_v4_ensemble.py"
```

默认推理：

```powershell
& "F:\Work\VSCode\Projects\DATASET\.venv\Scripts\python.exe" `
  "F:\Work\VSCode\Projects\DATASET\infer_binary_defect_v4.py" `
  "图片或图片目录" `
  --output "F:\Work\VSCode\Projects\DATASET\outputs\binary_defect_v4\inference"
```

高敏感模式：

```powershell
& "F:\Work\VSCode\Projects\DATASET\.venv\Scripts\python.exe" `
  "F:\Work\VSCode\Projects\DATASET\infer_binary_defect_v4.py" `
  "图片或图片目录" `
  --threshold 0.5882110080
```

## 关键产物

| 内容 | 路径 |
| --- | --- |
| 第一阶段最佳权重 | `runs/gear_yolo26n_496train_50val_fixed/weights/best.pt` |
| V4 三模型权重 | `outputs/binary_defect_v4/final_ensemble/` |
| V4 推理配置 | `outputs/binary_defect_v4/inference_config.json` |
| V4 最终报告 | `outputs/binary_defect_v4/final_report.json` |
| V4 逐图测试结果 | `outputs/binary_defect_v4/test_predictions.csv` |
| V4 候选排行榜 | `outputs/binary_defect_v4/leaderboard.csv` |
| 全部实验汇总 | `docs/实验方案与测试结果汇总.md` |

## 归档说明

历史代码位于 `archive/code/`：

- `stage1/`：最初的数据整理、YOLO 训练和训练后处理脚本。
- `v1/`：140 张双类模型和 211 张划痕模型脚本。
- `v2/`：V2 自动搜索、滑窗实验和最终评估脚本。

旧设计说明及配图位于 `archive/docs/v1-v3/`。归档代码保留用于追溯，部分脚本仍使用旧目录名 `DATASET/`，不保证从归档位置直接运行。

## 文档

- `docs/实验方案与测试结果汇总.md`：所有实验方案、指标和结论。
- `docs/README.md`：文档索引。
- `outputs/binary_defect_v4/README.md`：V4 结果与推理说明。
- `archive/README.md`：归档清单和使用限制。
