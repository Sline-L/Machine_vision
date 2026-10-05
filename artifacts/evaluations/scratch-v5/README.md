# Scratch V5 训练结果

- 最佳方案：`weighted_classifier_mean_a0.25`
- Recall：`0.977`
- Precision：`0.824`
- F1：`0.894`
- 正常误报率：`0.084`
- AUROC：`0.972`
- AUPRC：`0.937`
- 是否达到 Recall >= 0.95 且 FPR <= 0.20：`是`

本结果使用 val 同时选择模型与阈值，不是严格独立测试结果。

## 目录职责

本目录仅保存评估快照：指标、预测表、困难样本列表、图表和
`evaluation_config.json`。运行时使用的权重集中保存在 `model/model2/`，避免在评估产物中重复保存。

| 评估模型 | 部署文件 | SHA256 |
| --- | --- | --- |
| EfficientNet-B0 分类器 | `model/model2/classifier_1.pt` | `44461f4e03ff716266a3123bf1ba4611a1c965cf8776d0e523f128cf7c0b8438` |
| ResNet18 分类器 | `model/model2/classifier_2.pt` | `d07678a6da421c4edc00ac24b8c5052b0b8b7f8b1614b9d82563ecefbf59360d` |
| P2 划痕检测器 | `model/model2/detector.pt` | `4451e3f3664e3ad551926dc771e8cf4d0da9cd6648a9b841ea9d22bea86f15b3` |

`evaluation_config.json` 保留当时的 operating points，其权重路径相对于配置文件解析。
实际部署仍使用 `model/model2/inference_config.json`。
`leaderboard.*` 和 `final_report.json` 中的 `external://dataset/` 表示原训练工作区，
这些路径仅作为来源记录，不是本仓库内的可用文件。
