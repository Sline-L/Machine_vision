# joint_cls_yolo_cls_512

## 方法

- 任务：`normal/any_defect` 图像二分类。
- 模型：官方预训练 YOLO26n-cls，输入 512。
- 数据：统一模型固定拆分。
- 增强：关闭随机裁剪、AutoAugment 和擦除；比较验证 TTA 后选翻转 TTA。

## 验证结果

在 FPR <=20% 的工作点：Recall `0.7170`、Precision `0.9048`、F1 `0.8000`、FPR `0.1667`、AUROC `0.8294`、AUPRC `0.8765`，TP/FP/TN/FN=`38/4/20/15`。

该模型明显弱于 EfficientNet-B0，不进入最终精简单模型。

