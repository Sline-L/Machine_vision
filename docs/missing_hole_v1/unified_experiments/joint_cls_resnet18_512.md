# joint_cls_resnet18_512

## 方法

- 任务：`normal/any_defect` 图像二分类。
- 模型：官方预训练 ResNet18，输入 512。
- 数据：437 张可信图片，按近重复组拆成 360 train / 77 val。
- 训练：CUDA、AMP、类别均衡采样、非裁剪轻量增强、早停。

## 验证结果

在 FPR <=20% 的工作点：Recall `0.8868`、Precision `0.9216`、F1 `0.9038`、FPR `0.1667`、AUROC `0.8608`、AUPRC `0.9011`，TP/FP/TN/FN=`47/4/20/6`。

独立 test 未用于本候选选择。
