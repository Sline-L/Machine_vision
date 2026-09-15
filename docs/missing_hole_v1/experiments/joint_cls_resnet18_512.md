# joint_cls_resnet18_512

- 任务：scratch + missing_hole 统一模型
- 类型：`classifier`
- 输入：`512`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\joint_cls_resnet18_512\best.pt`

| Recall | Precision | F1 | FPR | TP/FP/TN/FN |
|---:|---:|---:|---:|---:|
| 0.8868 | 0.9216 | 0.9038 | 0.1667 | 47/4/20/6 |

该结果只使用联合验证集，独立 test 未读取。
