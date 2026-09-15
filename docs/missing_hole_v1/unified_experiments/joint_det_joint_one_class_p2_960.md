# joint_det_joint_one_class_p2_960

## 方法

- 任务：把 scratch 与 missing_hole 全部折叠成 `any_defect` 一个检测类别。
- 模型：YOLO26n-P2，输入 960，80 epochs。
- 数据：364 张双缺陷框监督完整的共同图片；311 train / 53 val。
- 选择：只看整图是否至少出现一个框，在 FPR <=20% 后最大化图像级 Recall。

## 验证结果

Recall `0.7241`、Precision `0.8400`、F1 `0.7778`、FPR `0.1667`、AUROC `0.8750`、AUPRC `0.8847`，TP/FP/TN/FN=`21/4/20/8`。

当允许 FPR `0.25` 时 Recall 可到 `0.9655`，但不满足主约束。
