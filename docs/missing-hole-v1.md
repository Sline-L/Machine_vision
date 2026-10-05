# Missing Hole V1 运行说明

Missing Hole V1 判断 Model1 齿轮 ROI 中是否存在缺齿或缺口。它由两个整图分类器和一个单类检测器组成，检测框仅用于人工复核。

```text
classifier_probability = (efficientnet_probability + resnet_probability) / 2
missing_hole_probability = 0.5 * classifier_probability + 0.5 * detector_probability
REJECT when missing_hole_probability >= 0.3413327979078584
```

模型包位于 `model/missing_hole_v1/`。配置使用相对路径并校验三份权重 SHA256；manifest 记录研究源提交和配置转换哈希。运行时启动时一次加载并预热三个模型，后续对每个 ROI 复用实例。

独立 test 共 150 张。专项结果为 Recall 0.8182、Precision 0.9000、FPR 0.0377，TP/FP/TN/FN 为 36/4/102/8。oblique Recall 只有 0.5882，是当前主要限制。

Scratch V5 与 Missing Hole V1 分别过阈值后按 OR 合并。联合 test 的任意缺陷 Recall 为 0.8873、FPR 为 0.2278，尚未达到 Recall 0.95 且 FPR 不超过 0.20 的目标。锁定 test 只能用于迁移回归，不能用于继续调阈值。

训练使用 Ultralytics 8.4.142，应用仓库内置版本标记为 8.4.13。本地已验证权重和检测类别可以加载；真实 CUDA 延迟、显存与端到端 ROI 效果仍需在目标 Jetson 上验收。
