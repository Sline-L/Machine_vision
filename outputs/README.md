# 输出产物目录

本目录保存训练、评估和推理产物。模型与文档依赖这些既有路径，因此按实验单元保留，不按文件扩展名拆分。

| 路径 | 内容 |
| --- | --- |
| `binary_defect_v4/` | V4 二分类模型、融合配置、报告与预测 |
| `scratch_v5/` | V5 划痕模型、锁定测试与错误分析 |
| `missing_hole_v1/` | 缺齿/缺口专项模型、测试与可视化 |
| `unified_defect_v1/` | 统一缺陷分类模型与配置 |
| `defect_search_v2/`、`defect_search_v3/` | 早期定位与搜索实验 |
| `test_predictions/`、`test_crops/` | 第一阶段逐图预测和检测框裁剪 |

根目录的 `post_training_summary.json` 和 `test_predictions.csv` 是第一阶段汇总文件。新增实验应建立独立的版本目录，避免覆盖现有基线。
