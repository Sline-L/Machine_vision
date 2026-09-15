# 二分类高召回缺陷模型 V4

## 模型用途

模型只判断整张齿轮图片是 `normal` 还是 `defect`。划痕和缺齿均视为缺陷，不输出缺陷类型和位置。

最终选择三模型融合：ResNet18 长训模型、不同随机种子的 YOLO26n-cls，以及 ResNet18 512 模型。每个模型分别完成温度缩放，融合时取三者缺陷概率最大值，以召回优先。

## 数据与训练

- 原始图片共 343 张：211 张缺陷、132 张正常。
- 拆分为 train 243、val 50、test 50。
- 共 159 个近重复组，dHash 距离小于等于 2 的跨集合泄漏为 0。
- 比较了 YOLO26n-cls、ResNet18、EfficientNet-B0，384/512 输入尺寸，以及缺陷权重 1/2/4。
- 共完成 18 个快速候选和 3 个长训候选，包括三个使用“灰度 + CLAHE + 拉普拉斯边缘”输入的纹理模型。
- 比较了原图、四路 TTA、不同随机种子、均值/最大值/排序均值融合，以及验证集阈值校准。
- 使用 RTX 4060、CUDA、AMP、RAM cache 和 4 workers。

## 留出集结果

默认阈值由验证集在正常误报率不超过 30% 的约束下选择：

| 指标 | 结果 |
| --- | ---: |
| 阈值 | 0.7028 |
| 缺陷 Recall | 0.633 |
| Precision | 0.731 |
| F1 | 0.679 |
| 正常误报率 | 0.350 |
| AUROC | 0.707 |
| AUPRC | 0.814 |
| TP / FP / TN / FN | 19 / 7 / 13 / 11 |

分组 Recall：划痕 0.364、缺齿 0.789、正视 0.556、斜视 0.615、侧视 0.750。相比扩展训练后的最佳单模型，融合将 Recall 从 0.467 提高到 0.633，但目标 Recall 0.95 仍未达到。

验证集上融合达到 Recall 0.933、误报率 0.25。由于最初基线结果已经用于判断后续实验方向，这次扩展后的留出集不再属于完全未查看的严格盲测；模型和阈值的具体选择仍只使用验证集。当前主要瓶颈是近重复分组后只有 50 张验证和 50 张留出图片，组间拍摄差异明显。

## 推理

默认模式：

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
  --threshold 0.5882110080 `
  --output "F:\Work\VSCode\Projects\DATASET\outputs\binary_defect_v4\inference_sensitive"
```

输出包括带判定文字的图片和 `predictions.csv`。当前模型适合辅助筛选与收集难例，不建议在未补充独立拍摄批次前直接承担无人值守剔除。建议优先补充当前漏检的低对比划痕，并以“拍摄批次”为单位划分数据。
