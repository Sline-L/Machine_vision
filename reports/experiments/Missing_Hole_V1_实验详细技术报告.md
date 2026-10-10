---
title: Missing Hole V1 实验详细技术报告
subtitle: 全实验参数 结果 权重来源 分类器与 YOLO 设计及与 V5 融合
date: 2026 年 9 月 30 日
lang: zh-CN
---

**文档性质：** Missing hole V1 全流程技术复盘、逐次实验归档、参数与权重溯源、锁定测试和 V5 联合方案审计  
**主要代码：** `prepare_missing_hole_v1.py`、`train_missing_hole_v1.py`、`train_unified_defect_v1.py`、`missing_hole_runtime.py`、`evaluate_missing_hole_v1_test.py`、`infer_gear_defects.py`  
**数据与运行证据：** `dataset_defects/missing_hole_v1`、`runs/missing_hole_v1`、`outputs/missing_hole_v1`、`outputs/unified_defect_v1`  
**审计日期：** 2026 年 9 月 30 日

## 目录

1. 核心结论
2. 任务定义与数据审计
3. 最终系统及权重
4. 总体实验设计与选择规则
5. 数据派生和标签方案
6. 完整公共训练参数
7. 34 次 Missing hole 专项实验
8. 21 次融合候选及最终权重来源
9. 锁定独立测试
10. 与 Scratch V5 的融合实验设计
11. 5 次统一缺陷模型实验
12. 参数和权重来源总表
13. 方法 算法与公式
14. 误差分析 风险与证据边界
15. 复现与产物索引

## 1 核心结论

Missing hole V1 的目标是从单张齿轮图像判断是否存在缺孔，并可输出辅助定位框。专项流程共完成 34 个正式候选：12 个 YOLO 检测先导、12 个分类器先导、3 个检测器 960 完整复训、3 个检测器 1280 对照、2 个分类器完整复训、1 个第二随机种子确认和 1 个难例精炼检测器。另完成 21 个验证集融合候选及 5 个 Scratch 与 Missing hole 统一模型候选。

最终 Missing hole 分数为：

`p_cls = (p_EfficientNet + p_ResNet) / 2`

`p_missing = 0.5 × p_cls + 0.5 × p_YOLO`

展开后：`p_missing = 0.25 × p_EfficientNet + 0.25 × p_ResNet + 0.50 × p_YOLO`。默认阈值为 `0.341332797907858`。这些是推理融合系数；它们与分类器损失正类权重、YOLO 的 box/cls/dfl 损失权重属于不同层级。

验证集 99 张上，专项融合 Recall=1.000、FPR=0.062。锁定测试集 150 张上，Recall=0.818、Precision=0.900、FPR=0.038，TP/FP/TN/FN=36/4/102/8。预设目标 Recall≥0.95 且 FPR≤0.20 没有达到，失败项是 Recall。8 个漏检中 7 个属于 oblique，说明测试分布的斜视缺口是主要瓶颈。

与 Scratch V5 的生产组合采用决策级 OR：Scratch 分数达到其锁定阈值，或 Missing hole 分数达到本报告阈值，就输出 REJECT。该组合在同一锁定 test 上对任意缺陷 Recall=0.887、FPR=0.228；高于统一 EfficientNet-B0 单模型的 Recall=0.761，但也超过 0.20 的 FPR 目标。因此现阶段更适合作为召回优先的辅助剔除或人工复核系统。

| 系统 | 评估集 | Recall | Precision | F1 | FPR | TP/FP/TN/FN | 结论 |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| Missing hole 专项融合 | val 99 | 1.000 | 0.895 | 0.944 | 0.062 | 34/4/61/0 | 验证集达到目标 |
| Missing hole 专项融合 | 锁定 test 150 | 0.818 | 0.900 | 0.857 | 0.038 | 36/4/102/8 | Recall 未达目标 |
| Scratch V5 与 Missing hole OR | 锁定 test 150 | 0.887 | 0.778 | 0.829 | 0.228 | 63/18/61/8 | 任意缺陷当前最佳 |
| 统一 EfficientNet-B0 | 锁定 test 150 | 0.761 | 0.621 | 0.684 | 0.418 | 54/33/46/17 | 小而简单但泛化较弱 |

## 2 任务定义与数据审计

标签 `y=1` 表示图像存在 missing hole；`y=0` 表示对 missing-hole 专项任务无缺孔。历史源目录仍叫 `missing_tooth`，本轮统一使用语义名 `missing_hole`。负样本允许含 scratch，因此它只能代表“无缺孔”，不能直接代表“完全正常”。

源训练池 496 张、173 张缺孔图、614 个框，其中 difficult 框 25 个。按近重复组和标签层次固定拆为 train 397 与 val 99，种子 20260913。独立 test 150 张、44 张缺孔图、168 个框，其中 difficult 框 6 个。

| split | 缺孔图 | 无缺孔图 | 总图数 | 框 | difficult 框 | bottom 图 | oblique 图 | side 图 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 139 | 258 | 397 | 498 | 21 | 43 | 49 | 59 |
| val | 34 | 65 | 99 | 116 | 4 | 11 | 12 | 14 |
| test | 44 | 106 | 150 | 168 | 6 | 12 | 17 | 20 |

数据准备逐项检查 XML 图像尺寸、类别集合、`difficult∈{0,1}`、边界框范围与 YOLO 归一化坐标。使用 SHA256、64 位 dHash、相邻编号、宽高比差和 32×32 灰度相关性建立 270 个近重复组。完全相同、dHash 距离≤2，或编号差≤2且宽高比相近、灰度相关系数≥0.985 的样本被并入同一组；同组不跨 train/val。训练池与独立 test 没有 SHA256 重复或 dHash 距离≤2 的跨集合近重复。

## 3 最终系统及权重

| 分支 | 来源实验 | 训练策略 | 输入 | TTA | 温度 T | 分支内权重 | 最终总权重 |
| --- | --- | --- | ---: | --- | ---: | ---: | ---: |
| 分类器 1 | `f_cls_efficientnet_b0_512_exclude_difficult_s20260913` | EfficientNet-B0，排除全 difficult 训练图 | 512 | none | 1.000 | 分类器均值内 0.5 | 0.25 |
| 分类器 2 | `f_cls_resnet18_384_include_difficult_s20260913` | ResNet18，保留 difficult | 384 | none | 2.375 | 分类器均值内 0.5 | 0.25 |
| 检测器 | `p_det_one_class_exclude_difficult_standard_960` | YOLO26n 标准头，单类，排除 difficult | 960 | none | 1.850 | 外层 0.5 | 0.50 |

检测器推理先用 `conf=0.001`、NMS IoU=0.7 保留候选框，再取整张图最大框置信度作为检测分支原始概率；经温度校准后进入融合。生产只把最终分数与 0.3413327979 比较。部署包中三个 Missing hole 权重约 16 MB、43 MB 和 5.2 MB，合计约 66.5 MB。

分类器和 YOLO 的“权重”需要分四层理解：

1. 网络参数权重来自 ImageNet/官方 YOLO 预训练初始化和本数据微调。
2. 自定义分类器损失使用正类权重 2.0 与 focal γ=1.5；这是设计先验，没有在 V1 中独立网格搜索。
3. YOLO 检测损失使用 box=7.5、cls=0.5、dfl=1.5；这是记录在 `args.yaml` 的训练配置，也没有在 V1 中做独立消融。
4. 最终 0.25/0.25/0.50 是验证集融合搜索结果，属于推理阶段权重。

## 4 总体实验设计与选择规则

所有模型、TTA、温度、融合规则和阈值只使用 val。模型排序键为：`(FPR≤0.20, Recall, 最差位置 Recall, −FPR, AUPRC)`。因此先满足 FPR 上限，再最大化召回；Recall 相同时优先保障 bottom/oblique/side 最差子组，然后降低 FPR，最后看 AUPRC。

实验按以下顺序执行：

1. 生成三类、两类、单类 × include/exclude difficult 共 6 套 YOLO 数据。
2. 进行 12 个检测先导：3 种标签 × 2 种 difficult 策略 × standard/P2，统一 960 和 35 epochs。
3. 进行 12 个分类先导：ResNet18、EfficientNet-B0、YOLO26n-cls × 384/512 × include/exclude difficult，统一 30 epochs。
4. 每种检测标签方案选出一个先导胜者，在 960 与 1280 分别完整训练 100 epochs；分类器选择前两名完整训练 100 epochs。
5. 对最佳方向执行第二种子确认；对最佳检测器执行 CLAHE 与难例重采样精炼。
6. 从所有完成候选中选前 2 个分类器和前 1 个检测器，搜索 21 个融合规则并锁定阈值。
7. 配置锁定后一次性读取独立 test；再以两个专项系统的固定阈值评估 Scratch V5 OR Missing hole V1。

## 5 数据派生和标签方案

| 标签方案 | 类别映射 | 用途 |
| --- | --- | --- |
| three_class | bottom→0，oblique→1，side→2 | 保留完整位置语义，检验多类监督是否有利 |
| two_class | bottom/oblique→0，side→1 | 合并相近角度，保留侧视差异 |
| one_class | bottom/oblique/side→0 | 只优化“是否缺孔”的图像级目标 |

`include_difficult` 保留全部训练框。`exclude_difficult` 只对训练集删除 difficult 框；若某张图的所有框都是 difficult，就整图排除，绝不把它误转成负样本。本次排除 6 张训练图，训练框从 498 降为 477；val/test 始终保留完整真值。

| 派生集 | train 图 | train 框 | 排除训练图 | val 图 | test 图 |
| --- | ---: | ---: | ---: | ---: | ---: |
| three_class include | 397 | 498 | 0 | 99 | 150 |
| three_class exclude | 391 | 477 | 6 | 99 | 150 |
| two_class include | 397 | 498 | 0 | 99 | 150 |
| two_class exclude | 391 | 477 | 6 | 99 | 150 |
| one_class include | 397 | 498 | 0 | 99 | 150 |
| one_class exclude | 391 | 477 | 6 | 99 | 150 |

## 6 完整公共训练参数

### 6.1 自定义 ResNet18 与 EfficientNet-B0

两类网络使用 torchvision ImageNet 默认预训练权重，末层替换为单输出 logit。图像保持长宽比缩放到 384 或 512 的正方形内，空白区域填充 RGB(238,238,238)，再按 ImageNet mean=(0.485,0.456,0.406)、std=(0.229,0.224,0.225) 标准化。

| 参数 | 值 |
| --- | --- |
| 优化器 | AdamW，lr=3e−4，weight_decay=5e−4 |
| 学习率 | CosineAnnealingLR，T_max=计划 epochs，eta_min=1e−6 |
| 损失 | FocalBCE，positive_weight=2.0，γ=1.5 |
| 采样 | WeightedRandomSampler，replacement=True，样本权重=1/同标签同位置组样本数 |
| batch | 384→24；512→12 |
| epoch/patience | pilot 30/12；full 或 confirmation 100/25；保存主排序最佳权重 |
| 增强 | 0.75 概率随机水平翻转、垂直翻转、±90°旋转；0.70 概率亮度 0.82–1.18 与对比度 0.80–1.22；CLAHE 0.25；高斯模糊 0.15、σ 0.1–1.0；高斯噪声 0.20、σ 1–5；JPEG 0.15、quality 65–92 |
| TTA 候选 | none；flip=原图+水平翻转+垂直翻转；rot90=原图+90°+270°，取均值 |
| 运行 | CUDA，AMP，pin_memory，persistent_workers，最多 8 workers，seed 20260913/确认实验 20260914 |

### 6.2 YOLO26n 分类器

官方 `yolo26n-cls.pt` 初始化。训练目录按 normal/missing_hole 构造；exclude 策略只排除 6 张全 difficult 训练图。参数：AdamW，lr0=7e−4，lrf=0.01，momentum=0.937，weight_decay=5e−4，warmup_epochs=3，warmup_momentum=0.8，warmup_bias_lr=0.1；输入 384/512，batch 24/12，workers=8，cache=ram，AMP；fliplr=0.5、flipud=0.5、hsv_h/s/v=0.003/0.08/0.18；degrees/translate/scale/shear/perspective=0；auto_augment=None，erasing=0。pilot 为 30 epochs、patience=12。TTA 与自定义分类器使用相同三候选。

`args.yaml` 中仍会显示 box/cls/dfl、mosaic、close_mosaic 等通用字段；对分类任务这些检测损失字段不构成实际框训练。不能把它们解释为分类器的正类权重。

### 6.3 YOLO26n 检测器

standard 使用官方 `yolo26n.pt`；P2 使用 Ultralytics `yolo26-p2.yaml` 建模并加载同一官方权重。共同参数：AdamW，lr0=7e−4，lrf=0.01，momentum=0.937，weight_decay=5e−4；warmup 3 epochs，warmup_momentum=0.8，warmup_bias_lr=0.1；box/cls/dfl=7.5/0.5/1.5；输入 960 时 batch=8、workers=8，输入 1280 时 batch=4、workers≤4；cache=ram，AMP；degrees=8、translate=0.03、scale=0.08、flipud=0.5、fliplr=0.5、hsv_h/s/v=0.003/0.08/0.18；mosaic/mixup/cutmix/copy_paste=0；close_mosaic=0；deterministic=False。

pilot 为 35 epochs、patience=12；full/refinement 为 100 epochs、patience=25。显存不足会逐次减半 batch；Windows OSError 22 会先降低 workers，再关闭 RAM cache 重试。推理 conf=0.001、NMS IoU=0.7，整图分数为最大框置信度。

## 7 34 次 Missing hole 专项实验

| 编号 | 实验 | 阶段 | 模型或方案 | 输入 | difficult | Recall | FPR | AUPRC |
| --- | --- | --- | --- | ---: | --- | ---: | ---: | ---: |
| E01 | p_det_three_class_include_difficult_standard_960 | pilot | three_class/standard | 960 | include_difficult | 0.912 | 0.123 | 0.951 |
| E02 | p_det_three_class_include_difficult_p2_960 | pilot | three_class/p2 | 960 | include_difficult | 0.941 | 0.108 | 0.947 |
| E03 | p_det_three_class_exclude_difficult_standard_960 | pilot | three_class/standard | 960 | exclude_difficult | 0.912 | 0.092 | 0.932 |
| E04 | p_det_three_class_exclude_difficult_p2_960 | pilot | three_class/p2 | 960 | exclude_difficult | 0.912 | 0.154 | 0.907 |
| E05 | p_det_two_class_include_difficult_standard_960 | pilot | two_class/standard | 960 | include_difficult | 0.912 | 0.108 | 0.909 |
| E06 | p_det_two_class_include_difficult_p2_960 | pilot | two_class/p2 | 960 | include_difficult | 0.941 | 0.108 | 0.922 |
| E07 | p_det_two_class_exclude_difficult_standard_960 | pilot | two_class/standard | 960 | exclude_difficult | 0.941 | 0.077 | 0.957 |
| E08 | p_det_two_class_exclude_difficult_p2_960 | pilot | two_class/p2 | 960 | exclude_difficult | 0.882 | 0.092 | 0.921 |
| E09 | p_det_one_class_include_difficult_standard_960 | pilot | one_class/standard | 960 | include_difficult | 0.971 | 0.185 | 0.966 |
| E10 | p_det_one_class_include_difficult_p2_960 | pilot | one_class/p2 | 960 | include_difficult | 0.882 | 0.123 | 0.945 |
| E11 | p_det_one_class_exclude_difficult_standard_960 | pilot | one_class/standard | 960 | exclude_difficult | 0.971 | 0.092 | 0.945 |
| E12 | p_det_one_class_exclude_difficult_p2_960 | pilot | one_class/p2 | 960 | exclude_difficult | 0.971 | 0.200 | 0.941 |
| E13 | p_cls_resnet18_384_include_difficult | pilot | resnet18 | 384 | include_difficult | 0.971 | 0.169 | 0.925 |
| E14 | p_cls_resnet18_384_exclude_difficult | pilot | resnet18 | 384 | exclude_difficult | 0.941 | 0.169 | 0.805 |
| E15 | p_cls_resnet18_512_include_difficult | pilot | resnet18 | 512 | include_difficult | 0.971 | 0.200 | 0.882 |
| E16 | p_cls_resnet18_512_exclude_difficult | pilot | resnet18 | 512 | exclude_difficult | 0.912 | 0.123 | 0.909 |
| E17 | p_cls_efficientnet_b0_384_include_difficult | pilot | efficientnet_b0 | 384 | include_difficult | 0.941 | 0.138 | 0.858 |
| E18 | p_cls_efficientnet_b0_384_exclude_difficult | pilot | efficientnet_b0 | 384 | exclude_difficult | 0.971 | 0.185 | 0.861 |
| E19 | p_cls_efficientnet_b0_512_include_difficult | pilot | efficientnet_b0 | 512 | include_difficult | 0.971 | 0.123 | 0.858 |
| E20 | p_cls_efficientnet_b0_512_exclude_difficult | pilot | efficientnet_b0 | 512 | exclude_difficult | 0.971 | 0.200 | 0.914 |
| E21 | p_cls_yolo_cls_384_include_difficult | pilot | yolo_cls | 384 | include_difficult | 0.853 | 0.200 | 0.749 |
| E22 | p_cls_yolo_cls_384_exclude_difficult | pilot | yolo_cls | 384 | exclude_difficult | 0.853 | 0.169 | 0.783 |
| E23 | p_cls_yolo_cls_512_include_difficult | pilot | yolo_cls | 512 | include_difficult | 0.676 | 0.154 | 0.730 |
| E24 | p_cls_yolo_cls_512_exclude_difficult | pilot | yolo_cls | 512 | exclude_difficult | 0.735 | 0.169 | 0.779 |
| E25 | f_det_three_class_include_difficult_p2_960 | full | three_class/p2 | 960 | include_difficult | 0.941 | 0.092 | 0.924 |
| E26 | f_det_two_class_exclude_difficult_standard_960 | full | two_class/standard | 960 | exclude_difficult | 0.912 | 0.092 | 0.905 |
| E27 | f_det_one_class_exclude_difficult_standard_960 | full | one_class/standard | 960 | exclude_difficult | 0.971 | 0.092 | 0.971 |
| E28 | f_cls_efficientnet_b0_512_exclude_difficult_s20260913 | full | efficientnet_b0 | 512 | exclude_difficult | 1.000 | 0.092 | 0.925 |
| E29 | f_cls_resnet18_384_include_difficult_s20260913 | full | resnet18 | 384 | include_difficult | 1.000 | 0.123 | 0.891 |
| E30 | confirm_efficientnet_b0_512_exclude_difficult_s20260914 | confirmation | efficientnet_b0 | 512 | exclude_difficult | 1.000 | 0.123 | 0.861 |
| E31 | f_det_three_class_include_difficult_p2_1280 | full | three_class/p2 | 1280 | include_difficult | 0.941 | 0.185 | 0.923 |
| E32 | f_det_two_class_exclude_difficult_standard_1280 | full | two_class/standard | 1280 | exclude_difficult | 0.941 | 0.185 | 0.948 |
| E33 | f_det_one_class_exclude_difficult_standard_1280 | full | one_class/standard | 1280 | exclude_difficult | 0.882 | 0.154 | 0.913 |
| E34 | refine_one_class_exclude_difficult_standard_960 | refinement | refined_one_class/standard | 960 | exclude_difficult | 0.941 | 0.108 | 0.951 |

以下每个实验均列出自身差异参数、真实训练长度、TTA、温度、四档阈值和验证结果。所有未重复的参数严格继承第 6 章；YOLO 的逐字段原始配置保存在相应 `runs/missing_hole_v1/<实验名>/args.yaml`。

### 7.1 p_det_three_class_include_difficult_standard_960

**内容与差异参数。** stage=`pilot`；seed=20260913；YOLO26n 标准检测头；标签=three_class；difficult=include_difficult；输入=960；batch=8；epoch 上限=35；patience=12。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 35 epochs；按 mAP50-95 回看最佳 epoch=29；框级 P/R/mAP50/mAP50-95=0.758/0.654/0.688/0.271。TTA=`none`；温度 T=1.475。FPR cap=0.20 主工作点：阈值=0.145945289，Recall/Precision/F1/FPR=0.912/0.795/0.849/0.123，AUROC/AUPRC=0.968/0.951，TP/FP/TN/FN=31/8/57/3。位置 Recall：bottom=0.818，oblique=0.917，side=1.000，difficult=0.333。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.191070150 | 0.882 | 0.833 | 0.857 | 0.092 | 30/6/59/4 |
| 0.2 | 0.145945289 | 0.912 | 0.795 | 0.849 | 0.123 | 31/8/57/3 |
| 0.3 | 0.052484389 | 1.000 | 0.694 | 0.819 | 0.231 | 34/15/50/0 |
| 0.5 | 0.052484389 | 1.000 | 0.694 | 0.819 | 0.231 | 34/15/50/0 |

**结论。** 该先导实验用于筛选标签方案、difficult 策略、架构或输入尺寸；结果保留为后续完整复训的依据。

### 7.2 p_det_three_class_include_difficult_p2_960

**内容与差异参数。** stage=`pilot`；seed=20260913；YOLO26 P2 小目标检测头；标签=three_class；difficult=include_difficult；输入=960；batch=8；epoch 上限=35；patience=12。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 35 epochs；按 mAP50-95 回看最佳 epoch=33；框级 P/R/mAP50/mAP50-95=0.641/0.452/0.492/0.164。TTA=`none`；温度 T=1.425。FPR cap=0.20 主工作点：阈值=0.124074386，Recall/Precision/F1/FPR=0.941/0.821/0.877/0.108，AUROC/AUPRC=0.959/0.947，TP/FP/TN/FN=32/7/58/2。位置 Recall：bottom=1.000，oblique=0.833，side=1.000，difficult=0.667。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.157886764 | 0.912 | 0.838 | 0.873 | 0.092 | 31/6/59/3 |
| 0.2 | 0.124074386 | 0.941 | 0.821 | 0.877 | 0.108 | 32/7/58/2 |
| 0.3 | 0.124074386 | 0.941 | 0.821 | 0.877 | 0.108 | 32/7/58/2 |
| 0.5 | 0.037146501 | 0.971 | 0.524 | 0.680 | 0.462 | 33/30/35/1 |

**结论。** 该先导实验用于筛选标签方案、difficult 策略、架构或输入尺寸；结果保留为后续完整复训的依据。

### 7.3 p_det_three_class_exclude_difficult_standard_960

**内容与差异参数。** stage=`pilot`；seed=20260913；YOLO26n 标准检测头；标签=three_class；difficult=exclude_difficult；输入=960；batch=8；epoch 上限=35；patience=12。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 35 epochs；按 mAP50-95 回看最佳 epoch=34；框级 P/R/mAP50/mAP50-95=0.826/0.593/0.684/0.277。TTA=`none`；温度 T=1.925。FPR cap=0.20 主工作点：阈值=0.108955405，Recall/Precision/F1/FPR=0.912/0.838/0.873/0.092，AUROC/AUPRC=0.957/0.932，TP/FP/TN/FN=31/6/59/3。位置 Recall：bottom=0.909，oblique=0.833，side=1.000，difficult=0.333。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.108955405 | 0.912 | 0.838 | 0.873 | 0.092 | 31/6/59/3 |
| 0.2 | 0.108955405 | 0.912 | 0.838 | 0.873 | 0.092 | 31/6/59/3 |
| 0.3 | 0.072140775 | 0.941 | 0.681 | 0.790 | 0.231 | 32/15/50/2 |
| 0.5 | 0.049399906 | 1.000 | 0.540 | 0.701 | 0.446 | 34/29/36/0 |

**结论。** 该先导实验用于筛选标签方案、difficult 策略、架构或输入尺寸；结果保留为后续完整复训的依据。

### 7.4 p_det_three_class_exclude_difficult_p2_960

**内容与差异参数。** stage=`pilot`；seed=20260913；YOLO26 P2 小目标检测头；标签=three_class；difficult=exclude_difficult；输入=960；batch=8；epoch 上限=35；patience=12。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 35 epochs；按 mAP50-95 回看最佳 epoch=36；框级 P/R/mAP50/mAP50-95=0.595/0.441/0.458/0.171。TTA=`none`；温度 T=2.175。FPR cap=0.20 主工作点：阈值=0.135967428，Recall/Precision/F1/FPR=0.912/0.756/0.827/0.154，AUROC/AUPRC=0.943/0.907，TP/FP/TN/FN=31/10/55/3。位置 Recall：bottom=0.818，oblique=0.917，side=1.000，difficult=0.000。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.227520988 | 0.853 | 0.853 | 0.853 | 0.077 | 29/5/60/5 |
| 0.2 | 0.135967428 | 0.912 | 0.756 | 0.827 | 0.154 | 31/10/55/3 |
| 0.3 | 0.100148528 | 0.941 | 0.627 | 0.753 | 0.292 | 32/19/46/2 |
| 0.5 | 0.086875776 | 0.971 | 0.623 | 0.759 | 0.308 | 33/20/45/1 |

**结论。** 该先导实验用于筛选标签方案、difficult 策略、架构或输入尺寸；结果保留为后续完整复训的依据。

### 7.5 p_det_two_class_include_difficult_standard_960

**内容与差异参数。** stage=`pilot`；seed=20260913；YOLO26n 标准检测头；标签=two_class；difficult=include_difficult；输入=960；batch=8；epoch 上限=35；patience=12。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 35 epochs；按 mAP50-95 回看最佳 epoch=36；框级 P/R/mAP50/mAP50-95=0.752/0.668/0.722/0.287。TTA=`none`；温度 T=1.825。FPR cap=0.20 主工作点：阈值=0.131293082，Recall/Precision/F1/FPR=0.912/0.816/0.861/0.108，AUROC/AUPRC=0.947/0.909，TP/FP/TN/FN=31/7/58/3。位置 Recall：bottom=0.909，oblique=0.833，side=1.000，difficult=0.667。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.163182650 | 0.882 | 0.882 | 0.882 | 0.062 | 30/4/61/4 |
| 0.2 | 0.131293082 | 0.912 | 0.816 | 0.861 | 0.108 | 31/7/58/3 |
| 0.3 | 0.131293082 | 0.912 | 0.816 | 0.861 | 0.108 | 31/7/58/3 |
| 0.5 | 0.054634657 | 0.971 | 0.589 | 0.733 | 0.354 | 33/23/42/1 |

**结论。** 该先导实验用于筛选标签方案、difficult 策略、架构或输入尺寸；结果保留为后续完整复训的依据。

### 7.6 p_det_two_class_include_difficult_p2_960

**内容与差异参数。** stage=`pilot`；seed=20260913；YOLO26 P2 小目标检测头；标签=two_class；difficult=include_difficult；输入=960；batch=8；epoch 上限=35；patience=12。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 35 epochs；按 mAP50-95 回看最佳 epoch=28；框级 P/R/mAP50/mAP50-95=0.542/0.310/0.395/0.157。TTA=`none`；温度 T=3.050。FPR cap=0.20 主工作点：阈值=0.206393190，Recall/Precision/F1/FPR=0.941/0.821/0.877/0.108，AUROC/AUPRC=0.952/0.922，TP/FP/TN/FN=32/7/58/2。位置 Recall：bottom=0.909，oblique=0.917，side=1.000，difficult=0.667。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.230104381 | 0.912 | 0.886 | 0.899 | 0.062 | 31/4/61/3 |
| 0.2 | 0.206393190 | 0.941 | 0.821 | 0.877 | 0.108 | 32/7/58/2 |
| 0.3 | 0.206393190 | 0.941 | 0.821 | 0.877 | 0.108 | 32/7/58/2 |
| 0.5 | 0.118998483 | 1.000 | 0.531 | 0.694 | 0.462 | 34/30/35/0 |

**结论。** 该先导实验用于筛选标签方案、difficult 策略、架构或输入尺寸；结果保留为后续完整复训的依据。

### 7.7 p_det_two_class_exclude_difficult_standard_960

**内容与差异参数。** stage=`pilot`；seed=20260913；YOLO26n 标准检测头；标签=two_class；difficult=exclude_difficult；输入=960；batch=8；epoch 上限=35；patience=12。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 35 epochs；按 mAP50-95 回看最佳 epoch=27；框级 P/R/mAP50/mAP50-95=0.788/0.635/0.736/0.307。TTA=`none`；温度 T=1.700。FPR cap=0.20 主工作点：阈值=0.150501567，Recall/Precision/F1/FPR=0.941/0.865/0.901/0.077，AUROC/AUPRC=0.966/0.957，TP/FP/TN/FN=32/5/60/2。位置 Recall：bottom=0.909，oblique=0.917，side=1.000，difficult=0.667。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.150501567 | 0.941 | 0.865 | 0.901 | 0.077 | 32/5/60/2 |
| 0.2 | 0.150501567 | 0.941 | 0.865 | 0.901 | 0.077 | 32/5/60/2 |
| 0.3 | 0.059570393 | 0.971 | 0.688 | 0.805 | 0.231 | 33/15/50/1 |
| 0.5 | 0.059570393 | 0.971 | 0.688 | 0.805 | 0.231 | 33/15/50/1 |

**结论。** 该先导实验用于筛选标签方案、difficult 策略、架构或输入尺寸；结果保留为后续完整复训的依据。

### 7.8 p_det_two_class_exclude_difficult_p2_960

**内容与差异参数。** stage=`pilot`；seed=20260913；YOLO26 P2 小目标检测头；标签=two_class；difficult=exclude_difficult；输入=960；batch=8；epoch 上限=35；patience=12。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 35 epochs；按 mAP50-95 回看最佳 epoch=36；框级 P/R/mAP50/mAP50-95=0.451/0.447/0.419/0.161。TTA=`none`；温度 T=2.650。FPR cap=0.20 主工作点：阈值=0.194249077，Recall/Precision/F1/FPR=0.882/0.833/0.857/0.092，AUROC/AUPRC=0.945/0.921，TP/FP/TN/FN=30/6/59/4。位置 Recall：bottom=0.818，oblique=0.833，side=1.000，difficult=0.333。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.194249077 | 0.882 | 0.833 | 0.857 | 0.092 | 30/6/59/4 |
| 0.2 | 0.194249077 | 0.882 | 0.833 | 0.857 | 0.092 | 30/6/59/4 |
| 0.3 | 0.126447483 | 0.941 | 0.653 | 0.771 | 0.262 | 32/17/48/2 |
| 0.5 | 0.097030322 | 1.000 | 0.523 | 0.687 | 0.477 | 34/31/34/0 |

**结论。** 该先导实验用于筛选标签方案、difficult 策略、架构或输入尺寸；结果保留为后续完整复训的依据。

### 7.9 p_det_one_class_include_difficult_standard_960

**内容与差异参数。** stage=`pilot`；seed=20260913；YOLO26n 标准检测头；标签=one_class；difficult=include_difficult；输入=960；batch=8；epoch 上限=35；patience=12。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 35 epochs；按 mAP50-95 回看最佳 epoch=26；框级 P/R/mAP50/mAP50-95=0.761/0.658/0.700/0.271。TTA=`none`；温度 T=2.000。FPR cap=0.20 主工作点：阈值=0.105833012，Recall/Precision/F1/FPR=0.971/0.733/0.835/0.185，AUROC/AUPRC=0.978/0.966，TP/FP/TN/FN=33/12/53/1。位置 Recall：bottom=0.909，oblique=1.000，side=1.000，difficult=0.667。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.163373867 | 0.912 | 0.912 | 0.912 | 0.046 | 31/3/62/3 |
| 0.2 | 0.105833012 | 0.971 | 0.733 | 0.835 | 0.185 | 33/12/53/1 |
| 0.3 | 0.074554264 | 1.000 | 0.654 | 0.791 | 0.277 | 34/18/47/0 |
| 0.5 | 0.074554264 | 1.000 | 0.654 | 0.791 | 0.277 | 34/18/47/0 |

**结论。** 该先导实验用于筛选标签方案、difficult 策略、架构或输入尺寸；结果保留为后续完整复训的依据。

### 7.10 p_det_one_class_include_difficult_p2_960

**内容与差异参数。** stage=`pilot`；seed=20260913；YOLO26 P2 小目标检测头；标签=one_class；difficult=include_difficult；输入=960；batch=8；epoch 上限=35；patience=12。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 35 epochs；按 mAP50-95 回看最佳 epoch=30；框级 P/R/mAP50/mAP50-95=0.603/0.457/0.533/0.185。TTA=`none`；温度 T=1.700。FPR cap=0.20 主工作点：阈值=0.155238326，Recall/Precision/F1/FPR=0.882/0.789/0.833/0.123，AUROC/AUPRC=0.962/0.945，TP/FP/TN/FN=30/8/57/4。位置 Recall：bottom=0.909，oblique=0.833，side=0.929，difficult=0.333。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.198304914 | 0.853 | 0.906 | 0.879 | 0.046 | 29/3/62/5 |
| 0.2 | 0.155238326 | 0.882 | 0.789 | 0.833 | 0.123 | 30/8/57/4 |
| 0.3 | 0.104259415 | 0.971 | 0.688 | 0.805 | 0.231 | 33/15/50/1 |
| 0.5 | 0.083283394 | 1.000 | 0.618 | 0.764 | 0.323 | 34/21/44/0 |

**结论。** 该先导实验用于筛选标签方案、difficult 策略、架构或输入尺寸；结果保留为后续完整复训的依据。

### 7.11 p_det_one_class_exclude_difficult_standard_960

**内容与差异参数。** stage=`pilot`；seed=20260913；YOLO26n 标准检测头；标签=one_class；difficult=exclude_difficult；输入=960；batch=8；epoch 上限=35；patience=12。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 35 epochs；按 mAP50-95 回看最佳 epoch=35；框级 P/R/mAP50/mAP50-95=0.825/0.647/0.669/0.265。TTA=`none`；温度 T=1.850。FPR cap=0.20 主工作点：阈值=0.120594500，Recall/Precision/F1/FPR=0.971/0.846/0.904/0.092，AUROC/AUPRC=0.974/0.945，TP/FP/TN/FN=33/6/59/1。位置 Recall：bottom=1.000，oblique=0.917，side=1.000，difficult=1.000。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.120594500 | 0.971 | 0.846 | 0.904 | 0.092 | 33/6/59/1 |
| 0.2 | 0.120594500 | 0.971 | 0.846 | 0.904 | 0.092 | 33/6/59/1 |
| 0.3 | 0.061734870 | 1.000 | 0.694 | 0.819 | 0.231 | 34/15/50/0 |
| 0.5 | 0.061734870 | 1.000 | 0.694 | 0.819 | 0.231 | 34/15/50/0 |

**结论。** 最终检测器。虽然是 35 epoch 先导权重，但按 Recall、最差位置 Recall、FPR 的既定排序优于后续完整复训检测器。

### 7.12 p_det_one_class_exclude_difficult_p2_960

**内容与差异参数。** stage=`pilot`；seed=20260913；YOLO26 P2 小目标检测头；标签=one_class；difficult=exclude_difficult；输入=960；batch=8；epoch 上限=35；patience=12。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 35 epochs；按 mAP50-95 回看最佳 epoch=31；框级 P/R/mAP50/mAP50-95=0.728/0.388/0.486/0.181。TTA=`none`；温度 T=1.750。FPR cap=0.20 主工作点：阈值=0.081824422，Recall/Precision/F1/FPR=0.971/0.717/0.825/0.200，AUROC/AUPRC=0.967/0.941，TP/FP/TN/FN=33/13/52/1。位置 Recall：bottom=1.000，oblique=0.917，side=1.000，difficult=1.000。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.201065944 | 0.882 | 0.909 | 0.896 | 0.046 | 30/3/62/4 |
| 0.2 | 0.081824422 | 0.971 | 0.717 | 0.825 | 0.200 | 33/13/52/1 |
| 0.3 | 0.070981905 | 1.000 | 0.654 | 0.791 | 0.277 | 34/18/47/0 |
| 0.5 | 0.070981905 | 1.000 | 0.654 | 0.791 | 0.277 | 34/18/47/0 |

**结论。** 该先导实验用于筛选标签方案、difficult 策略、架构或输入尺寸；结果保留为后续完整复训的依据。

### 7.13 p_cls_resnet18_384_include_difficult

**内容与差异参数。** stage=`pilot`；seed=20260913；resnet18；difficult=include_difficult；输入=384；batch=24；epoch 上限=30；patience=12。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 30 epochs；主排序最佳 epoch=25；该轮原始 Recall/FPR/Precision=0.971/0.169/0.750；末轮 loss=0.013865。TTA=`none`；温度 T=0.950。FPR cap=0.20 主工作点：阈值=0.357916433，Recall/Precision/F1/FPR=0.971/0.750/0.846/0.169，AUROC/AUPRC=0.960/0.925，TP/FP/TN/FN=33/11/54/1。位置 Recall：bottom=1.000，oblique=0.917，side=1.000，difficult=1.000。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.611650981 | 0.882 | 0.833 | 0.857 | 0.092 | 30/6/59/4 |
| 0.2 | 0.357916433 | 0.971 | 0.750 | 0.846 | 0.169 | 33/11/54/1 |
| 0.3 | 0.357916433 | 0.971 | 0.750 | 0.846 | 0.169 | 33/11/54/1 |
| 0.5 | 0.144243812 | 1.000 | 0.576 | 0.731 | 0.385 | 34/25/40/0 |

**结论。** 该先导实验用于筛选标签方案、difficult 策略、架构或输入尺寸；结果保留为后续完整复训的依据。

### 7.14 p_cls_resnet18_384_exclude_difficult

**内容与差异参数。** stage=`pilot`；seed=20260913；resnet18；difficult=exclude_difficult；输入=384；batch=24；epoch 上限=30；patience=12。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 20 epochs；主排序最佳 epoch=8；该轮原始 Recall/FPR/Precision=0.941/0.169/0.744；末轮 loss=0.036172。TTA=`none`；温度 T=2.200。FPR cap=0.20 主工作点：阈值=0.614766355，Recall/Precision/F1/FPR=0.941/0.744/0.831/0.169，AUROC/AUPRC=0.925/0.805，TP/FP/TN/FN=32/11/54/2。位置 Recall：bottom=0.818，oblique=1.000，side=1.000，difficult=1.000。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.668312370 | 0.824 | 0.903 | 0.862 | 0.046 | 28/3/62/6 |
| 0.2 | 0.614766355 | 0.941 | 0.744 | 0.831 | 0.169 | 32/11/54/2 |
| 0.3 | 0.614766355 | 0.941 | 0.744 | 0.831 | 0.169 | 32/11/54/2 |
| 0.5 | 0.571060161 | 0.971 | 0.550 | 0.702 | 0.415 | 33/27/38/1 |

**结论。** 该先导实验用于筛选标签方案、difficult 策略、架构或输入尺寸；结果保留为后续完整复训的依据。

### 7.15 p_cls_resnet18_512_include_difficult

**内容与差异参数。** stage=`pilot`；seed=20260913；resnet18；difficult=include_difficult；输入=512；batch=12；epoch 上限=30；patience=12。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 20 epochs；主排序最佳 epoch=8；该轮原始 Recall/FPR/Precision=0.971/0.200/0.717；末轮 loss=0.045214。TTA=`none`；温度 T=1.250。FPR cap=0.20 主工作点：阈值=0.601346432，Recall/Precision/F1/FPR=0.971/0.717/0.825/0.200，AUROC/AUPRC=0.936/0.882，TP/FP/TN/FN=33/13/52/1。位置 Recall：bottom=0.909，oblique=1.000，side=1.000，difficult=1.000。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.659782649 | 0.765 | 0.812 | 0.788 | 0.092 | 26/6/59/8 |
| 0.2 | 0.601346432 | 0.971 | 0.717 | 0.825 | 0.200 | 33/13/52/1 |
| 0.3 | 0.601346432 | 0.971 | 0.717 | 0.825 | 0.200 | 33/13/52/1 |
| 0.5 | 0.589490991 | 1.000 | 0.618 | 0.764 | 0.323 | 34/21/44/0 |

**结论。** 该先导实验用于筛选标签方案、difficult 策略、架构或输入尺寸；结果保留为后续完整复训的依据。

### 7.16 p_cls_resnet18_512_exclude_difficult

**内容与差异参数。** stage=`pilot`；seed=20260913；resnet18；difficult=exclude_difficult；输入=512；batch=12；epoch 上限=30；patience=12。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 30 epochs；主排序最佳 epoch=22；该轮原始 Recall/FPR/Precision=0.912/0.123/0.795；末轮 loss=0.020296。TTA=`none`；温度 T=1.075。FPR cap=0.20 主工作点：阈值=0.665023459，Recall/Precision/F1/FPR=0.912/0.795/0.849/0.123，AUROC/AUPRC=0.949/0.909，TP/FP/TN/FN=31/8/57/3。位置 Recall：bottom=0.818，oblique=0.917，side=1.000，difficult=1.000。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.756456608 | 0.853 | 0.853 | 0.853 | 0.077 | 29/5/60/5 |
| 0.2 | 0.665023459 | 0.912 | 0.795 | 0.849 | 0.123 | 31/8/57/3 |
| 0.3 | 0.570082959 | 0.941 | 0.696 | 0.800 | 0.215 | 32/14/51/2 |
| 0.5 | 0.270524381 | 1.000 | 0.548 | 0.708 | 0.431 | 34/28/37/0 |

**结论。** 该先导实验用于筛选标签方案、difficult 策略、架构或输入尺寸；结果保留为后续完整复训的依据。

### 7.17 p_cls_efficientnet_b0_384_include_difficult

**内容与差异参数。** stage=`pilot`；seed=20260913；efficientnet_b0；difficult=include_difficult；输入=384；batch=24；epoch 上限=30；patience=12。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 25 epochs；主排序最佳 epoch=13；该轮原始 Recall/FPR/Precision=0.941/0.138/0.780；末轮 loss=0.012273。TTA=`none`；温度 T=0.875。FPR cap=0.20 主工作点：阈值=0.423336502，Recall/Precision/F1/FPR=0.941/0.780/0.853/0.138，AUROC/AUPRC=0.931/0.858，TP/FP/TN/FN=32/9/56/2。位置 Recall：bottom=0.818，oblique=1.000，side=1.000，difficult=1.000。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.511412769 | 0.912 | 0.838 | 0.873 | 0.092 | 31/6/59/3 |
| 0.2 | 0.423336502 | 0.941 | 0.780 | 0.853 | 0.138 | 32/9/56/2 |
| 0.3 | 0.423336502 | 0.941 | 0.780 | 0.853 | 0.138 | 32/9/56/2 |
| 0.5 | 0.423336502 | 0.941 | 0.780 | 0.853 | 0.138 | 32/9/56/2 |

**结论。** 该先导实验用于筛选标签方案、difficult 策略、架构或输入尺寸；结果保留为后续完整复训的依据。

### 7.18 p_cls_efficientnet_b0_384_exclude_difficult

**内容与差异参数。** stage=`pilot`；seed=20260913；efficientnet_b0；difficult=exclude_difficult；输入=384；batch=24；epoch 上限=30；patience=12。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 23 epochs；主排序最佳 epoch=11；该轮原始 Recall/FPR/Precision=0.971/0.185/0.733；末轮 loss=0.033925。TTA=`none`；温度 T=0.850。FPR cap=0.20 主工作点：阈值=0.404373457，Recall/Precision/F1/FPR=0.971/0.733/0.835/0.185，AUROC/AUPRC=0.952/0.861，TP/FP/TN/FN=33/12/53/1。位置 Recall：bottom=0.909，oblique=1.000，side=1.000，difficult=1.000。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.544405800 | 0.882 | 0.909 | 0.896 | 0.046 | 30/3/62/4 |
| 0.2 | 0.404373457 | 0.971 | 0.733 | 0.835 | 0.185 | 33/12/53/1 |
| 0.3 | 0.374303011 | 1.000 | 0.708 | 0.829 | 0.215 | 34/14/51/0 |
| 0.5 | 0.374303011 | 1.000 | 0.708 | 0.829 | 0.215 | 34/14/51/0 |

**结论。** 该先导实验用于筛选标签方案、difficult 策略、架构或输入尺寸；结果保留为后续完整复训的依据。

### 7.19 p_cls_efficientnet_b0_512_include_difficult

**内容与差异参数。** stage=`pilot`；seed=20260913；efficientnet_b0；difficult=include_difficult；输入=512；batch=12；epoch 上限=30；patience=12。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 22 epochs；主排序最佳 epoch=10；该轮原始 Recall/FPR/Precision=0.971/0.123/0.805；末轮 loss=0.014527。TTA=`none`；温度 T=1.675。FPR cap=0.20 主工作点：阈值=0.601171301，Recall/Precision/F1/FPR=0.971/0.805/0.880/0.123，AUROC/AUPRC=0.945/0.858，TP/FP/TN/FN=33/8/57/1。位置 Recall：bottom=0.909，oblique=1.000，side=1.000，difficult=0.667。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.658662201 | 0.941 | 0.865 | 0.901 | 0.077 | 32/5/60/2 |
| 0.2 | 0.601171301 | 0.971 | 0.805 | 0.880 | 0.123 | 33/8/57/1 |
| 0.3 | 0.601171301 | 0.971 | 0.805 | 0.880 | 0.123 | 33/8/57/1 |
| 0.5 | 0.601171301 | 0.971 | 0.805 | 0.880 | 0.123 | 33/8/57/1 |

**结论。** 该先导实验用于筛选标签方案、difficult 策略、架构或输入尺寸；结果保留为后续完整复训的依据。

### 7.20 p_cls_efficientnet_b0_512_exclude_difficult

**内容与差异参数。** stage=`pilot`；seed=20260913；efficientnet_b0；difficult=exclude_difficult；输入=512；batch=12；epoch 上限=30；patience=12。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 28 epochs；主排序最佳 epoch=16；该轮原始 Recall/FPR/Precision=0.971/0.200/0.717；末轮 loss=0.010857。TTA=`none`；温度 T=0.950。FPR cap=0.20 主工作点：阈值=0.303995802，Recall/Precision/F1/FPR=0.971/0.717/0.825/0.200，AUROC/AUPRC=0.957/0.914，TP/FP/TN/FN=33/13/52/1。位置 Recall：bottom=1.000，oblique=1.000，side=0.929，difficult=1.000。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.600002020 | 0.853 | 0.829 | 0.841 | 0.092 | 29/6/59/5 |
| 0.2 | 0.303995802 | 0.971 | 0.717 | 0.825 | 0.200 | 33/13/52/1 |
| 0.3 | 0.298743662 | 1.000 | 0.694 | 0.819 | 0.231 | 34/15/50/0 |
| 0.5 | 0.298743662 | 1.000 | 0.694 | 0.819 | 0.231 | 34/15/50/0 |

**结论。** 该先导实验用于筛选标签方案、difficult 策略、架构或输入尺寸；结果保留为后续完整复训的依据。

### 7.21 p_cls_yolo_cls_384_include_difficult

**内容与差异参数。** stage=`pilot`；seed=20260913；yolo_cls；difficult=include_difficult；输入=384；batch=24；epoch 上限=30；patience=12。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 20 epochs；最高 top1=0.859，位于 epoch=9；该轮 train/val loss=0.207/0.350。TTA=`none`；温度 T=4.000。FPR cap=0.20 主工作点：阈值=0.810404600，Recall/Precision/F1/FPR=0.853/0.690/0.763/0.200，AUROC/AUPRC=0.871/0.749，TP/FP/TN/FN=29/13/52/5。位置 Recall：bottom=0.818，oblique=0.833，side=0.929，difficult=0.667。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.863781595 | 0.559 | 0.760 | 0.644 | 0.092 | 19/6/59/15 |
| 0.2 | 0.810404600 | 0.853 | 0.690 | 0.763 | 0.200 | 29/13/52/5 |
| 0.3 | 0.801250915 | 0.882 | 0.638 | 0.741 | 0.262 | 30/17/48/4 |
| 0.5 | 0.781169615 | 0.941 | 0.604 | 0.736 | 0.323 | 32/21/44/2 |

**结论。** YOLO26n-cls 的 Recall 与 AUPRC 整体低于 torchvision 分类器，未进入最终分类器集合。

### 7.22 p_cls_yolo_cls_384_exclude_difficult

**内容与差异参数。** stage=`pilot`；seed=20260913；yolo_cls；difficult=exclude_difficult；输入=384；batch=24；epoch 上限=30；patience=12。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 19 epochs；最高 top1=0.859，位于 epoch=8；该轮 train/val loss=0.155/0.603。TTA=`rot90`；温度 T=4.000。FPR cap=0.20 主工作点：阈值=0.673955574，Recall/Precision/F1/FPR=0.853/0.725/0.784/0.169，AUROC/AUPRC=0.881/0.783，TP/FP/TN/FN=29/11/54/5。位置 Recall：bottom=0.636，oblique=0.917，side=1.000，difficult=0.667。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.720218680 | 0.559 | 0.792 | 0.655 | 0.077 | 19/5/60/15 |
| 0.2 | 0.673955574 | 0.853 | 0.725 | 0.784 | 0.169 | 29/11/54/5 |
| 0.3 | 0.647128209 | 0.912 | 0.633 | 0.747 | 0.277 | 31/18/47/3 |
| 0.5 | 0.641711245 | 0.941 | 0.615 | 0.744 | 0.308 | 32/20/45/2 |

**结论。** YOLO26n-cls 的 Recall 与 AUPRC 整体低于 torchvision 分类器，未进入最终分类器集合。

### 7.23 p_cls_yolo_cls_512_include_difficult

**内容与差异参数。** stage=`pilot`；seed=20260913；yolo_cls；difficult=include_difficult；输入=512；batch=12；epoch 上限=30；patience=12。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 30 epochs；最高 top1=0.879，位于 epoch=25；该轮 train/val loss=0.063/0.616。TTA=`flip`；温度 T=4.000。FPR cap=0.20 主工作点：阈值=0.733935030，Recall/Precision/F1/FPR=0.676/0.697/0.687/0.154，AUROC/AUPRC=0.838/0.730，TP/FP/TN/FN=23/10/55/11。位置 Recall：bottom=0.545，oblique=0.583，side=0.929，difficult=0.333。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.805687569 | 0.471 | 0.762 | 0.582 | 0.077 | 16/5/60/18 |
| 0.2 | 0.733935030 | 0.676 | 0.697 | 0.687 | 0.154 | 23/10/55/11 |
| 0.3 | 0.667195920 | 0.735 | 0.581 | 0.649 | 0.277 | 25/18/47/9 |
| 0.5 | 0.564408558 | 0.941 | 0.525 | 0.674 | 0.446 | 32/29/36/2 |

**结论。** YOLO26n-cls 的 Recall 与 AUPRC 整体低于 torchvision 分类器，未进入最终分类器集合。

### 7.24 p_cls_yolo_cls_512_exclude_difficult

**内容与差异参数。** stage=`pilot`；seed=20260913；yolo_cls；difficult=exclude_difficult；输入=512；batch=12；epoch 上限=30；patience=12。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 28 epochs；最高 top1=0.848，位于 epoch=17；该轮 train/val loss=0.110/0.380。TTA=`flip`；温度 T=4.000。FPR cap=0.20 主工作点：阈值=0.847413975，Recall/Precision/F1/FPR=0.735/0.694/0.714/0.169，AUROC/AUPRC=0.856/0.779，TP/FP/TN/FN=25/11/54/9。位置 Recall：bottom=0.818，oblique=0.667，side=0.786，difficult=0.333。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.880340954 | 0.500 | 0.773 | 0.607 | 0.077 | 17/5/60/17 |
| 0.2 | 0.847413975 | 0.735 | 0.694 | 0.714 | 0.169 | 25/11/54/9 |
| 0.3 | 0.801149970 | 0.794 | 0.587 | 0.675 | 0.292 | 27/19/46/7 |
| 0.5 | 0.734963659 | 0.941 | 0.516 | 0.667 | 0.462 | 32/30/35/2 |

**结论。** YOLO26n-cls 的 Recall 与 AUPRC 整体低于 torchvision 分类器，未进入最终分类器集合。

### 7.25 f_det_three_class_include_difficult_p2_960

**内容与差异参数。** stage=`full`；seed=20260913；YOLO26 P2 小目标检测头；标签=three_class；difficult=include_difficult；输入=960；batch=8；epoch 上限=100；patience=25。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 99 epochs；按 mAP50-95 回看最佳 epoch=75；框级 P/R/mAP50/mAP50-95=0.667/0.564/0.627/0.243。TTA=`none`；温度 T=3.400。FPR cap=0.20 主工作点：阈值=0.281108315，Recall/Precision/F1/FPR=0.941/0.842/0.889/0.092，AUROC/AUPRC=0.943/0.924，TP/FP/TN/FN=32/6/59/2。位置 Recall：bottom=0.909，oblique=0.917，side=1.000，difficult=0.667。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.281108315 | 0.941 | 0.842 | 0.889 | 0.092 | 32/6/59/2 |
| 0.2 | 0.281108315 | 0.941 | 0.842 | 0.889 | 0.092 | 32/6/59/2 |
| 0.3 | 0.281108315 | 0.941 | 0.842 | 0.889 | 0.092 | 32/6/59/2 |
| 0.5 | 0.281108315 | 0.941 | 0.842 | 0.889 | 0.092 | 32/6/59/2 |

**结论。** 该实验完成了正式对照，但按预先定义的验证集排序规则未进入最终融合。

### 7.26 f_det_two_class_exclude_difficult_standard_960

**内容与差异参数。** stage=`full`；seed=20260913；YOLO26n 标准检测头；标签=two_class；difficult=exclude_difficult；输入=960；batch=8；epoch 上限=100；patience=25。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 100 epochs；按 mAP50-95 回看最佳 epoch=76；框级 P/R/mAP50/mAP50-95=0.813/0.721/0.743/0.327。TTA=`none`；温度 T=2.750。FPR cap=0.20 主工作点：阈值=0.244687744，Recall/Precision/F1/FPR=0.912/0.838/0.873/0.092，AUROC/AUPRC=0.943/0.905，TP/FP/TN/FN=31/6/59/3。位置 Recall：bottom=0.909，oblique=0.833，side=1.000，difficult=0.667。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.244687744 | 0.912 | 0.838 | 0.873 | 0.092 | 31/6/59/3 |
| 0.2 | 0.244687744 | 0.912 | 0.838 | 0.873 | 0.092 | 31/6/59/3 |
| 0.3 | 0.117595268 | 0.941 | 0.681 | 0.790 | 0.231 | 32/15/50/2 |
| 0.5 | 0.083749921 | 0.971 | 0.569 | 0.717 | 0.385 | 33/25/40/1 |

**结论。** 该实验完成了正式对照，但按预先定义的验证集排序规则未进入最终融合。

### 7.27 f_det_one_class_exclude_difficult_standard_960

**内容与差异参数。** stage=`full`；seed=20260913；YOLO26n 标准检测头；标签=one_class；difficult=exclude_difficult；输入=960；batch=8；epoch 上限=100；patience=25。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 96 epochs；按 mAP50-95 回看最佳 epoch=72；框级 P/R/mAP50/mAP50-95=0.781/0.724/0.751/0.315。TTA=`none`；温度 T=2.850。FPR cap=0.20 主工作点：阈值=0.171855116，Recall/Precision/F1/FPR=0.971/0.846/0.904/0.092，AUROC/AUPRC=0.978/0.971，TP/FP/TN/FN=33/6/59/1。位置 Recall：bottom=0.909，oblique=1.000，side=1.000，difficult=0.667。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.171855116 | 0.971 | 0.846 | 0.904 | 0.092 | 33/6/59/1 |
| 0.2 | 0.171855116 | 0.971 | 0.846 | 0.904 | 0.092 | 33/6/59/1 |
| 0.3 | 0.171855116 | 0.971 | 0.846 | 0.904 | 0.092 | 33/6/59/1 |
| 0.5 | 0.171855116 | 0.971 | 0.846 | 0.904 | 0.092 | 33/6/59/1 |

**结论。** 该实验完成了正式对照，但按预先定义的验证集排序规则未进入最终融合。

### 7.28 f_cls_efficientnet_b0_512_exclude_difficult_s20260913

**内容与差异参数。** stage=`full`；seed=20260913；efficientnet_b0；difficult=exclude_difficult；输入=512；batch=12；epoch 上限=100；patience=25。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 54 epochs；主排序最佳 epoch=29；该轮原始 Recall/FPR/Precision=1.000/0.092/0.850；末轮 loss=0.005251。TTA=`none`；温度 T=1.000。FPR cap=0.20 主工作点：阈值=0.380999386，Recall/Precision/F1/FPR=1.000/0.850/0.919/0.092，AUROC/AUPRC=0.970/0.925，TP/FP/TN/FN=34/6/59/0。位置 Recall：bottom=1.000，oblique=1.000，side=1.000，difficult=1.000。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.380999386 | 1.000 | 0.850 | 0.919 | 0.092 | 34/6/59/0 |
| 0.2 | 0.380999386 | 1.000 | 0.850 | 0.919 | 0.092 | 34/6/59/0 |
| 0.3 | 0.380999386 | 1.000 | 0.850 | 0.919 | 0.092 | 34/6/59/0 |
| 0.5 | 0.380999386 | 1.000 | 0.850 | 0.919 | 0.092 | 34/6/59/0 |

**结论。** 最终分类器 1。完整复训后验证 Recall 1.000、FPR 0.092；在入选分类器中 FPR 最低。

### 7.29 f_cls_resnet18_384_include_difficult_s20260913

**内容与差异参数。** stage=`full`；seed=20260913；resnet18；difficult=include_difficult；输入=384；batch=24；epoch 上限=100；patience=25。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 38 epochs；主排序最佳 epoch=13；该轮原始 Recall/FPR/Precision=1.000/0.123/0.810；末轮 loss=0.025740。TTA=`none`；温度 T=2.375。FPR cap=0.20 主工作点：阈值=0.625503272，Recall/Precision/F1/FPR=1.000/0.810/0.895/0.123，AUROC/AUPRC=0.964/0.891，TP/FP/TN/FN=34/8/57/0。位置 Recall：bottom=1.000，oblique=1.000，side=1.000，difficult=1.000。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.651635608 | 0.941 | 0.865 | 0.901 | 0.077 | 32/5/60/2 |
| 0.2 | 0.625503272 | 1.000 | 0.810 | 0.895 | 0.123 | 34/8/57/0 |
| 0.3 | 0.625503272 | 1.000 | 0.810 | 0.895 | 0.123 | 34/8/57/0 |
| 0.5 | 0.625503272 | 1.000 | 0.810 | 0.895 | 0.123 | 34/8/57/0 |

**结论。** 最终分类器 2。它与 EfficientNet 使用不同骨干和 difficult 策略，提供互补误差模式。

### 7.30 confirm_efficientnet_b0_512_exclude_difficult_s20260914

**内容与差异参数。** stage=`confirmation`；seed=20260914；efficientnet_b0；difficult=exclude_difficult；输入=512；batch=12；epoch 上限=100；patience=25。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 52 epochs；主排序最佳 epoch=27；该轮原始 Recall/FPR/Precision=1.000/0.123/0.810；末轮 loss=0.007991。TTA=`none`；温度 T=1.450。FPR cap=0.20 主工作点：阈值=0.336824537，Recall/Precision/F1/FPR=1.000/0.810/0.895/0.123，AUROC/AUPRC=0.958/0.861，TP/FP/TN/FN=34/8/57/0。位置 Recall：bottom=1.000，oblique=1.000，side=1.000，difficult=1.000。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.840733876 | 0.794 | 0.900 | 0.844 | 0.046 | 27/3/62/7 |
| 0.2 | 0.336824537 | 1.000 | 0.810 | 0.895 | 0.123 | 34/8/57/0 |
| 0.3 | 0.336824537 | 1.000 | 0.810 | 0.895 | 0.123 | 34/8/57/0 |
| 0.5 | 0.336824537 | 1.000 | 0.810 | 0.895 | 0.123 | 34/8/57/0 |

**结论。** 第二随机种子仍达到 Recall 1.000，确认结构方向；FPR 和 AUPRC 弱于首个完整复训，未替换部署权重。

### 7.31 f_det_three_class_include_difficult_p2_1280

**内容与差异参数。** stage=`full`；seed=20260913；YOLO26 P2 小目标检测头；标签=three_class；difficult=include_difficult；输入=1280；batch=4；epoch 上限=100；patience=25。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 100 epochs；按 mAP50-95 回看最佳 epoch=84；框级 P/R/mAP50/mAP50-95=0.588/0.622/0.593/0.253。TTA=`none`；温度 T=3.075。FPR cap=0.20 主工作点：阈值=0.150371711，Recall/Precision/F1/FPR=0.941/0.727/0.821/0.185，AUROC/AUPRC=0.948/0.923，TP/FP/TN/FN=32/12/53/2。位置 Recall：bottom=0.909，oblique=0.917，side=1.000，difficult=0.667。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.289502452 | 0.912 | 0.912 | 0.912 | 0.046 | 31/3/62/3 |
| 0.2 | 0.150371711 | 0.941 | 0.727 | 0.821 | 0.185 | 32/12/53/2 |
| 0.3 | 0.150371711 | 0.941 | 0.727 | 0.821 | 0.185 | 32/12/53/2 |
| 0.5 | 0.150371711 | 0.941 | 0.727 | 0.821 | 0.185 | 32/12/53/2 |

**结论。** 1280 输入没有形成稳定收益，且 batch 与 worker 必须降低；不进入部署配置。

### 7.32 f_det_two_class_exclude_difficult_standard_1280

**内容与差异参数。** stage=`full`；seed=20260913；YOLO26n 标准检测头；标签=two_class；difficult=exclude_difficult；输入=1280；batch=4；epoch 上限=100；patience=25。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 68 epochs；按 mAP50-95 回看最佳 epoch=44；框级 P/R/mAP50/mAP50-95=0.831/0.680/0.760/0.313。TTA=`none`；温度 T=2.550。FPR cap=0.20 主工作点：阈值=0.142377097，Recall/Precision/F1/FPR=0.941/0.727/0.821/0.185，AUROC/AUPRC=0.964/0.948，TP/FP/TN/FN=32/12/53/2。位置 Recall：bottom=0.909，oblique=0.917，side=1.000，difficult=0.333。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.287818222 | 0.882 | 0.857 | 0.870 | 0.077 | 30/5/60/4 |
| 0.2 | 0.142377097 | 0.941 | 0.727 | 0.821 | 0.185 | 32/12/53/2 |
| 0.3 | 0.105768133 | 0.971 | 0.702 | 0.815 | 0.215 | 33/14/51/1 |
| 0.5 | 0.105768133 | 0.971 | 0.702 | 0.815 | 0.215 | 33/14/51/1 |

**结论。** 1280 输入没有形成稳定收益，且 batch 与 worker 必须降低；不进入部署配置。

### 7.33 f_det_one_class_exclude_difficult_standard_1280

**内容与差异参数。** stage=`full`；seed=20260913；YOLO26n 标准检测头；标签=one_class；difficult=exclude_difficult；输入=1280；batch=4；epoch 上限=100；patience=25。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 52 epochs；按 mAP50-95 回看最佳 epoch=28；框级 P/R/mAP50/mAP50-95=0.798/0.612/0.678/0.291。TTA=`none`；温度 T=3.625。FPR cap=0.20 主工作点：阈值=0.239181605，Recall/Precision/F1/FPR=0.882/0.750/0.811/0.154，AUROC/AUPRC=0.930/0.913，TP/FP/TN/FN=30/10/55/4。位置 Recall：bottom=0.818，oblique=0.917，side=0.929，difficult=0.333。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.352111032 | 0.765 | 0.897 | 0.825 | 0.046 | 26/3/62/8 |
| 0.2 | 0.239181605 | 0.882 | 0.750 | 0.811 | 0.154 | 30/10/55/4 |
| 0.3 | 0.205121740 | 0.912 | 0.660 | 0.765 | 0.246 | 31/16/49/3 |
| 0.5 | 0.172524452 | 0.941 | 0.615 | 0.744 | 0.308 | 32/20/45/2 |

**结论。** 1280 输入没有形成稳定收益，且 batch 与 worker 必须降低；不进入部署配置。

### 7.34 refine_one_class_exclude_difficult_standard_960

**内容与差异参数。** stage=`refinement`；seed=20260913；YOLO26n 标准检测头；标签=refined_one_class；difficult=exclude_difficult；输入=960；batch=8；epoch 上限=100；patience=25。其余参数完整继承第 6 章相应模型族配置。

**训练与结果。** 训练记录 100 epochs；按 mAP50-95 回看最佳 epoch=81；框级 P/R/mAP50/mAP50-95=0.843/0.707/0.756/0.348。TTA=`none`；温度 T=3.225。FPR cap=0.20 主工作点：阈值=0.348918603，Recall/Precision/F1/FPR=0.941/0.821/0.877/0.108，AUROC/AUPRC=0.960/0.951，TP/FP/TN/FN=32/7/58/2。位置 Recall：bottom=0.909，oblique=0.917，side=1.000，difficult=0.667。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 0.387297803 | 0.912 | 0.886 | 0.899 | 0.062 | 31/4/61/3 |
| 0.2 | 0.348918603 | 0.941 | 0.821 | 0.877 | 0.108 | 32/7/58/2 |
| 0.3 | 0.348918603 | 0.941 | 0.821 | 0.877 | 0.108 | 32/7/58/2 |
| 0.5 | 0.348918603 | 0.941 | 0.821 | 0.877 | 0.108 | 32/7/58/2 |

**结论。** CLAHE 与难例复制后的精炼实验没有超过基础单类标准检测器。


## 8 21 次融合候选及最终权重来源

候选生成先按主排序选出两个分类器和一个检测器：完整 EfficientNet-B0 512 exclude、完整 ResNet18 384 include、先导单类 standard YOLO 960 exclude。基础候选包括三个单模型、分类器 mean、分类器 max，共 5 个。对 4 个非 detector 分类候选，分别加入检测器加权 α∈{0.25,0.50,0.75} 和 soft-OR，因此总数为 `5+4×4=21`。

加权公式中 α 表示分类器候选的权重：`p=α p_cls+(1−α)p_det`。soft-OR 为 `max(p_cls,p_det)`。每个候选直接在校准后的验证概率上重新选择阈值并按同一排序规则比较。

| 编号 | 融合候选 | 阈值 | Recall | Precision | FPR | AUPRC | TP/FP/TN/FN |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| F01 | f_cls_efficientnet_b0_512_exclude_difficult_s20260913 | 0.380999386 | 1.000 | 0.850 | 0.092 | 0.925 | 34/6/59/0 |
| F02 | f_cls_resnet18_384_include_difficult_s20260913 | 0.625503272 | 1.000 | 0.810 | 0.123 | 0.891 | 34/8/57/0 |
| F03 | p_det_one_class_exclude_difficult_standard_960 | 0.120594500 | 0.971 | 0.846 | 0.092 | 0.945 | 33/6/59/1 |
| F04 | classifier_mean | 0.525113819 | 1.000 | 0.872 | 0.077 | 0.895 | 34/5/60/0 |
| F05 | classifier_max | 0.651635608 | 1.000 | 0.850 | 0.092 | 0.926 | 34/6/59/0 |
| F06 | weighted_f_cls_efficientnet_b0_512_exclude_difficult_s20260913_0.25 | 0.205996503 | 1.000 | 0.895 | 0.062 | 0.963 | 34/4/61/0 |
| F07 | weighted_f_cls_efficientnet_b0_512_exclude_difficult_s20260913_0.5 | 0.268682324 | 1.000 | 0.872 | 0.077 | 0.963 | 34/5/60/0 |
| F08 | weighted_f_cls_efficientnet_b0_512_exclude_difficult_s20260913_0.75 | 0.331368145 | 1.000 | 0.872 | 0.077 | 0.950 | 34/5/60/0 |
| F09 | soft_or_f_cls_efficientnet_b0_512_exclude_difficult_s20260913 | 0.380999386 | 1.000 | 0.850 | 0.092 | 0.926 | 34/6/59/0 |
| F10 | weighted_f_cls_resnet18_384_include_difficult_s20260913_0.25 | 0.210271870 | 1.000 | 0.829 | 0.108 | 0.970 | 34/7/58/0 |
| F11 | weighted_f_cls_resnet18_384_include_difficult_s20260913_0.5 | 0.358808869 | 1.000 | 0.829 | 0.108 | 0.966 | 34/7/58/0 |
| F12 | weighted_f_cls_resnet18_384_include_difficult_s20260913_0.75 | 0.507345869 | 1.000 | 0.829 | 0.108 | 0.943 | 34/7/58/0 |
| F13 | soft_or_f_cls_resnet18_384_include_difficult_s20260913 | 0.637849081 | 1.000 | 0.791 | 0.138 | 0.893 | 34/9/56/0 |
| F14 | weighted_classifier_mean_0.25 | 0.217594736 | 1.000 | 0.872 | 0.077 | 0.966 | 34/5/60/0 |
| F15 | weighted_classifier_mean_0.5 | 0.341332798 | 1.000 | 0.895 | 0.062 | 0.966 | 34/4/61/0 |
| F16 | weighted_classifier_mean_0.75 | 0.451701947 | 1.000 | 0.872 | 0.077 | 0.953 | 34/5/60/0 |
| F17 | soft_or_classifier_mean | 0.562071095 | 1.000 | 0.872 | 0.077 | 0.895 | 34/5/60/0 |
| F18 | weighted_classifier_max_0.25 | 0.224917602 | 1.000 | 0.850 | 0.092 | 0.965 | 34/6/59/0 |
| F19 | weighted_classifier_max_0.5 | 0.386115054 | 1.000 | 0.872 | 0.077 | 0.965 | 34/5/60/0 |
| F20 | weighted_classifier_max_0.75 | 0.518875331 | 1.000 | 0.850 | 0.092 | 0.954 | 34/6/59/0 |
| F21 | soft_or_classifier_max | 0.651635608 | 1.000 | 0.850 | 0.092 | 0.926 | 34/6/59/0 |

最终选择 `weighted_classifier_mean_0.5`。它与 `weighted_EfficientNet_0.25` 都达到 Recall 1.000、FPR 0.0615，但前者 AUPRC=0.966，高于后者 0.963，因此在前序排序项相同后胜出。由此得到分类器集合外层权重 0.5、检测器权重 0.5；分类器内部均值再把 0.5 平分，所以最终总系数为 0.25/0.25/0.50。

## 9 锁定独立测试

最终配置 SHA256 为 `b33a87326a440640dd868bac46aa87535231cf1b947ca5905f59eeaffa5a5f9c`，测试 manifest SHA256 为 `317f49feb65d81ad4b4767bd553ff59bd01ba95b2bef9302d1e9939ce2e7de3b`。评估于 2026-09-13 17:07:01 创建锁文件；权重、温度、融合和阈值均在读取 test 前选定。

| 口径 | 图 | 正/负 | Recall | Precision | F1 | FPR | NPV | AUROC | AUPRC | TP/FP/TN/FN |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 包含 difficult | 150 | 44/106 | 0.818 | 0.900 | 0.857 | 0.038 | 0.927 | 0.892 | 0.899 | 36/4/102/8 |
| 忽略 difficult | 149 | 43/106 | 0.814 | 0.897 | 0.854 | 0.038 | 0.927 | 0.890 | 0.896 | 35/4/102/8 |
| 纯易样本 | 145 | 39/106 | 0.821 | 0.889 | 0.853 | 0.038 | 0.936 | 0.881 | 0.886 | 32/4/102/7 |

| 位置 | 缺陷图 | Recall | 解释 |
| --- | ---: | ---: | --- |
| bottom | 12 | 0.917 | 漏检 1 张，为 difficult 的 test_140 |
| oblique | 17 | 0.588 | 漏检 7 张，是总体召回下降的主因 |
| side | 20 | 1.000 | 当前 test 全部命中 |

8 个 FN 为 test_064、065、121、124、125、127、128（均为 oblique）以及 test_140（bottom，difficult）。4 个 FP 为 test_035、047、057、068。`test_047.xml` 没有对象，因此按无缺孔处理。

检测器以 0.024708 的低原始置信度做辅助定位时，class-agnostic Recall@IoU0.3=0.601、Precision=0.416；Recall@IoU0.5=0.554、Precision=0.383。class-aware mAP50=0.501，mAP50-95=0.209。最终决策依赖图像级融合分数，框级结果只用于解释和复核。

![锁定测试中的 oblique 示例](/home/Sline/Work/VSCode/Projects/Machine_vision/outputs/missing_hole_v1/test/visualizations/oblique_test_011.jpg){width=78%}

## 10 与 Scratch V5 的融合实验设计

### 10.1 双专项 OR

Scratch V5 自己的内部融合为 `0.125×EfficientNet + 0.125×ResNet18 + 0.75×YOLO-P2`，阈值 0.3002736103。Missing hole V1 内部融合为 `0.25×EfficientNet + 0.25×ResNet18 + 0.50×YOLO-standard`，阈值 0.3413327979。两个概率分别对不同缺陷定义、不同数据与不同温度校准，因此跨任务不再做数值平均。

联合决策为：

`reject_scratch = [p_scratch ≥ 0.3002736103]`

`reject_missing = [p_missing ≥ 0.3413327979]`

`REJECT = reject_scratch OR reject_missing`

同一 test 有 scratch 31 张、missing hole 44 张、任意缺陷 71 张、两种缺陷同时存在 4 张、任意缺陷均无 79 张。OR 系统对 scratch Recall=0.8065，对 missing-hole Recall=0.9318；后者高于 Missing hole 专项自身的 0.8182，是因为部分 Missing hole 漏检图被 Scratch 分支补回。任意缺陷总体 TP/FP/TN/FN=63/18/61/8，Recall=0.8873、FPR=0.2278。

这里没有从 test 搜索新的 OR 权重或阈值。它只把两个已锁定专项系统组合后评估，因此结果是方案评估证据，而不是新的调参结果。若要降低 0.228 的 FPR，必须建立新的联合验证集后再设计门控或阈值，不能回用当前锁定 test。

### 10.2 统一模型对照

统一模型实验构造 437 张可靠联合数据：364 张同时具有 Scratch 和 Missing hole 完整监督的图像，加 73 张额外明确 Missing hole 正样本；59 张 Scratch 状态未知且 Missing hole 阴性的候选被排除。分类器标签为“scratch 或 missing hole”；检测器只用 364 张双任务监督完整图。

统一模型与双专项 OR 的比较回答两个问题：是否可用一个更小的模型替代约 130 MB 的双专项系统，以及共享特征是否改善任意缺陷泛化。测试结果显示统一 EfficientNet-B0 只有 15.6 MB，但 Recall 0.761、FPR 0.418，暂时不能替代双专项系统。

## 11 5 次统一缺陷模型实验

分类器统一使用输入 512、80 epochs、patience=25 和第 6.1/6.2 节训练配置；检测器使用 P2、960、80 epochs、patience=25 和第 6.3 节参数。验证集规模为 77 张，其中正类 53、负类 24；检测器验证只覆盖 364 张完整监督数据对应的子集。

| 编号 | 实验 | 类型 | 家族/标签 | 输入 | 实际 epoch | TTA | 温度 | 阈值 | Recall | Precision | FPR | AUPRC |
| --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| U01 | joint_cls_resnet18_512 | classifier | resnet18 | 512 | 27 | none | 0.600 | 0.701733145 | 0.887 | 0.922 | 0.167 | 0.901 |
| U02 | joint_cls_efficientnet_b0_512 | classifier | efficientnet_b0 | 512 | 37 | none | 1.125 | 0.676499797 | 0.943 | 0.926 | 0.167 | 0.945 |
| U03 | joint_cls_yolo_cls_512 | classifier | yolo_cls | 512 | 28 | flip | 3.350 | 0.709724839 | 0.717 | 0.905 | 0.167 | 0.877 |
| U04 | joint_det_joint_one_class_p2_960 | detector | joint_one_class | 960 | 75 | none | 3.675 | 0.347514041 | 0.724 | 0.840 | 0.167 | 0.885 |
| U05 | joint_det_joint_two_class_p2_960 | detector | joint_two_class | 960 | 70 | none | 3.200 | 0.416072266 | 0.655 | 0.826 | 0.167 | 0.847 |

统一模型按同一验证排序选择 `joint_cls_efficientnet_b0_512`：TTA=none、T=1.125、阈值=0.6764997973。验证 Recall=0.9434、FPR=0.1667；锁定 test 上 Recall=0.7606、FPR=0.4177，表现明显低于双专项 OR。

## 12 参数和权重来源总表

| 参数或权重 | 最终值 | 来源实验或方法 | 证据解释 |
| --- | --- | --- | --- |
| train/val 划分 | 397/99，seed 20260913 | 近重复组分层搜索 2000 次 | 最小化总量与各标签层偏差，同组不跨 split |
| 标签方案 | 检测器用 one_class | 12 个检测先导对照 | 单类直接优化是否缺孔，验证 Recall/FPR 最优组合 |
| 检测头 | standard | standard vs P2 先导 | 单类 exclude 下两者 Recall 同为 0.971，standard FPR 0.092 低于 P2 的 0.200 |
| YOLO 输入 | 960 | 960 vs 1280 完整复训 | 单类 1280 Recall 0.882/FPR 0.154，弱于 960 |
| YOLO difficult 策略 | exclude | include/exclude 全因子先导 | 单类 standard exclude 在同 Recall 下 FPR 低于 include |
| 最终 YOLO checkpoint | `p_det_one_class_exclude_difficult_standard_960` | 全候选主排序 | 最差位置 Recall、FPR 优先级使先导权重胜过 full/refine |
| 分类器家族 | EfficientNet-B0 + ResNet18 | 12 个先导与 2 个 full | 两个 full 均 Recall 1.0，架构差异带来互补 |
| 分类器输入 | 512 与 384 | 384/512 先导 | EfficientNet 选 512；ResNet 选 384；分别由主排序决定 |
| 分类器 difficult | exclude 与 include | include/exclude 先导 | 两个入选分类器采用不同策略，保留互补性 |
| 分类器损失正类权重 | 2.0 | 代码预设 | V1 未独立搜索，不能声称由对照实验求得 |
| Focal γ | 1.5 | 代码预设 | V1 未独立搜索 |
| 分层采样权重 | 1/n(y,group) | 逆频率 WeightedRandomSampler | 平衡 normal 与 bottom/oblique/side 组合组 |
| YOLO box/cls/dfl | 7.5/0.5/1.5 | Ultralytics 训练配置 | 未在 V1 独立消融；属于检测损失先验 |
| 温度 | 1.000/2.375/1.850 | 147 点温度网格 | 在 val 最小化 NLL；范围 0.35–4.0、步长 0.025 |
| TTA | 三个最终分支均 none | none/flip/rot90 比较 | 每个分类器按主排序选择；检测器未使用 TTA |
| 分类器内部权重 | 0.5/0.5 | mean 与 max 候选 | 分类器 mean 进入最终融合 |
| 分类器/检测器权重 | 0.5/0.5 | α=0.25/0.5/0.75 与 soft-OR 搜索 | 21 候选中 weighted_classifier_mean_0.5 胜出 |
| 最终总权重 | 0.25/0.25/0.50 | 两层融合展开 | EfficientNet/ResNet/YOLO |
| Missing hole 阈值 | 0.3413327979 | val 概率候选穷举 | 在 FPR≤0.20 下按 Recall、FPR、Precision 选取 |
| 与 V5 的跨任务权重 | 无标量权重 | 决策级 OR | 各专项先独立校准和阈值化，再做逻辑或 |
| 统一模型权重 | EfficientNet-B0 单模型 | 5 个 joint 候选 | 验证最佳但 test 不足以替代双专项系统 |

## 13 方法 算法与公式

### 13.1 Focal BCE

对 logit `z`，`p=σ(z)`，普通二元交叉熵为 `BCE=−[y log p+(1−y)log(1−p)]`。令 `p_t=yp+(1−y)(1−p)`，类别权重 `w_y=2` 当 y=1，否则 1，则：

`L = mean[w_y × (1−p_t)^1.5 × BCE]`

正类权重提高缺陷样本梯度，focal 因子压低已被正确分类的易样本。二者是训练损失设计，不能与最终融合系数相加或互换。

### 13.2 逆频率分层采样

训练样本按 `(label, group)` 分层，其中 group 是 bottom、oblique、side 的组合或 normal。第 i 个样本的采样权重为 `w_i=1/n_(y_i,g_i)`，WeightedRandomSampler 有放回采样固定长度。这让小位置组更常出现，但不改变损失中的 positive_weight=2.0。

### 13.3 余弦学习率

`η_t=η_min+0.5(η_0−η_min)[1+cos(πt/T_max)]`，其中自定义分类器 `η_0=3×10⁻⁴`、`η_min=10⁻⁶`。早停发生时，实际训练可能早于完整余弦周期结束。

### 13.4 温度缩放

先把概率转为 logit：`l=log[p/(1−p)]`，再计算 `p_T=σ(l/T)`。在 `T∈{0.35,0.375,…,4.0}` 的 147 点网格上最小化：

`NLL(T)=−(1/N)Σ[y log p_T+(1−y)log(1−p_T)]`

温度不改变单模型内部排序，但会改变跨模型融合后的相对贡献，因此必须在融合前固定。

### 13.5 阈值与排序

阈值候选是 `(0, 1)∪{验证集概率}`。对每个候选计算 Recall、Precision、FPR，并按 `(FPR≤cap, Recall, −FPR, Precision)` 取最大值。模型级排序再加入最差位置 Recall 和 AUPRC。由于 val 只有 34 个正类、65 个负类，Recall 和 FPR 最小步长分别为 1/34≈0.0294 与 1/65≈0.0154。

### 13.6 融合与 OR

Missing hole 两层线性融合：`p_m=0.5×[(p_e+p_r)/2]+0.5p_d`。Scratch 与 Missing hole 的跨任务组合是布尔 OR：`reject=(p_s≥τ_s)∨(p_m≥τ_m)`。OR 能提高任意缺陷召回，但正常图只要被任一分支误报就会成为 FP，因此系统 FPR 通常上升。

### 13.7 IoU 与 mAP

`IoU(A,B)=|A∩B|/|A∪B|`。框级 Recall@IoU0.3/0.5 用置信度排序和一对一匹配统计；mAP50 是 IoU=0.5 下各类 AP，mAP50-95 是 0.50 到 0.95、步长 0.05 的平均。图像级主任务只取最大框分数，不要求类别或框位置正确。

## 14 误差分析 风险与证据边界

验证 Recall 1.000 到 test Recall 0.818 的落差说明当前 34 个验证正类不足以覆盖真实 oblique 变化。oblique test 17 张只命中 10 张；继续加 epoch、改 1280 或重复 CLAHE 已经被本轮实验否定，优先级应转向补拍斜视缺陷与相同视角的反光正常负样本。

difficult 不是总体瓶颈：test 中含 difficult 框的 5 张图命中 4 张；包含 difficult、忽略 difficult、纯易样本三种 Recall 都约 0.81。排除 difficult 的训练策略仍可能有益，因为含糊框会增加训练噪声，但它不等于模型无法识别 difficult 样本。

框级定位显著弱于图像级判定，低阈值产生较多 FP 框。0.50 的检测器融合权重只说明最大框置信度有图像级判别价值，不能解释为定位可靠。生产 UI 应把框标为辅助提示。

融合、温度、TTA、模型和阈值都使用同一 val，存在验证集过拟合风险。第二种子确认保持 Recall 1.000，但 AUPRC 从 0.925 降到 0.861；这进一步说明单次验证分数不稳定。当前 test 已锁定，后续不能回用它重新选择模型。

GPU 运行环境为 NVIDIA GeForce RTX 4060 Laptop GPU、CUDA 13.0、PyTorch 2.14.0+cu130，AMP 与 RAM cache 开启。监控 1735 个采样点，平均 GPU 利用率约 83.9%、峰值 100%，平均显存 3957 MiB、峰值 5882 MiB，最高温度 80°C。1280 在 Windows 多进程加载失败时自动降低 worker 后重试。

## 15 复现与产物索引

```powershell
& ".venv\Scripts\python.exe" "prepare_missing_hole_v1.py"
& ".venv\Scripts\python.exe" "train_missing_hole_v1.py" --workers 8
& ".venv\Scripts\python.exe" "train_unified_defect_v1.py"
& ".venv\Scripts\python.exe" "evaluate_missing_hole_v1_test.py"
& ".venv\Scripts\python.exe" "infer_gear_defects.py" "图片或目录"
```

| 证据 | 路径 | 作用 |
| --- | --- | --- |
| 数据准备 | `prepare_missing_hole_v1.py` | 审计、分组、拆分、六套标签派生 |
| 专项训练 | `train_missing_hole_v1.py` | 34 实验、温度、阈值、21 融合候选 |
| 联合训练 | `train_unified_defect_v1.py` | 5 个任意缺陷统一模型候选 |
| 运行时 | `missing_hole_runtime.py` | 模型推理、温度和融合规则 |
| 双专项推理 | `infer_gear_defects.py` | Scratch 与 Missing hole 的 OR 判定 |
| 锁定评估 | `evaluate_missing_hole_v1_test.py` | test 指标、框指标、联合系统对照 |
| 数据清单 | `dataset_defects/missing_hole_v1/master_manifest.csv` | 逐图标签、框、hash、split |
| 数据预检 | `dataset_defects/missing_hole_v1/preflight_report.json` | 数量、重复组、六套派生统计 |
| 专项排行榜 | `outputs/missing_hole_v1/leaderboard.json` | 34 次实验完整结果 |
| 融合排行榜 | `outputs/missing_hole_v1/fusion_leaderboard.json` | 21 个融合候选 |
| 部署配置 | `outputs/missing_hole_v1/inference_config.json` | 三权重、温度、融合、阈值 |
| 独立测试 | `outputs/missing_hole_v1/test/test_report.json` | 图像级、框级与 V5 合并结果 |
| 统一模型 | `outputs/unified_defect_v1/leaderboard.json` | 5 次 joint 实验 |
| 原始参数 | `runs/missing_hole_v1/*/args.yaml` | YOLO 每次运行的完整 CLI 字段 |
| 训练轨迹 | `runs/missing_hole_v1/*/history.json` / `results.csv` | epoch、loss、top1、mAP |

本报告的证据优先级为：锁定 `test_report.json` 和最终 `inference_config.json` 决定部署与测试结论；`leaderboard.json` 和 `fusion_leaderboard.json` 决定实验选择；`args.yaml`、`history.json`、`results.csv` 决定真实训练配置和轨迹；总结性 Markdown 用于交叉核对。Windows 绝对路径是历史运行痕迹，最终部署包使用相对路径。
