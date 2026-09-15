# 齿轮缺陷识别 V3、V4、V5 与 Missing Hole V1 总实验流程报告

更新时间：2026-09-13

## 1. 报告目的与结论摘要

本文统一整理四轮核心实验的目标、数据、训练流程、配置、候选模型、选择规则、验证结果、独立测试结果和失败经验，并逐项核对 `docs/优化方案.md` 中提出的优化方向。

四轮实验不是在同一数据和同一评价口径上进行，不能只看一个 Recall 数字直接排序：

- V3、V4 使用早期 343 张数据，包含 `scratch`、`missing_tooth` 和 normal。
- V5 使用重新整理后的 514 张 scratch 专项数据。
- Missing Hole V1 使用 496 张训练池和 150 张独立测试图，标签重构为 `bottom`、`oblique`、`side`。
- V3 和 Missing Hole V1 的测试集在模型锁定后只评估一次；V5 也有独立测试。V4 扩展方向参考过早期测试结果，因此其最终留出集不再是严格盲测。

### 1.1 最重要的最终结果

| 版本 | 任务 | 最终评估 Recall | Precision | FPR | 评估性质与结论 |
| --- | --- | ---: | ---: | ---: | --- |
| V3 | scratch 图像级判定 | 0.364 | 1.000 | 0.150（系统整体） | 锁定测试；划痕泛化很弱 |
| V3 | missing_tooth 图像级判定 | 0.789 | 0.750 | 0.150（系统整体） | 锁定测试；可辅助复核，未达 0.90 |
| V4 | 任意缺陷二分类融合 | 0.633 | 0.731 | 0.350 | 历史留出评估；扩展方向已参考过该批数据 |
| V5 | scratch 专项融合 | 0.806 | 0.556 | 0.168 | 锁定测试；FPR 达标，Recall 未达 0.95 |
| Missing Hole V1 | missing_hole 专项融合 | 0.818 | 0.900 | 0.038 | 锁定测试；精度高，主要漏检 oblique |
| 专项 OR | scratch 或 missing_hole | 0.887 | 0.778 | 0.228 | 同一锁定测试；当前任意缺陷最佳方案 |
| 统一模型 | 任意缺陷单分类器 | 0.761 | 0.621 | 0.418 | 同一锁定测试；简单但明显弱于专项 OR |

### 1.2 总体认识

1. 缺陷是否可见、独立样本数量和拍摄分布，比继续增加 epoch 更重要。
2. 单独训练 scratch 与 missing_hole，再使用 OR 合并，明显优于一个统一模型。
3. P2 对微小目标不是必然更好：V5 选中了 P2 辅助检测器，但 Missing Hole V1 的最佳检测器是 standard。
4. 960 提升到 1280、CLAHE 加难例重采样、普通滑窗等方法都没有稳定改善泛化。
5. 验证集高分不等于生产效果。V5 与 Missing Hole V1 均出现验证 Recall 接近或达到 1.0，但独立测试 Recall 约 0.81。

## 2. 统一评价口径

### 2.1 图像级指标

- Recall = TP / (TP + FN)：所有真实缺陷图中被识别出来的比例，是本项目第一优先级。
- Precision = TP / (TP + FP)：模型判为缺陷的图片中真实缺陷所占比例。
- FPR = FP / (FP + TN)：正常齿轮被误判为缺陷的比例，即正常误剔除率。
- F1：Precision 与 Recall 的调和平均。
- AUROC：模型对正负样本整体排序能力。
- AUPRC：Precision-Recall 曲线下面积，更适合类别不均衡且关注缺陷类的场景。
- NPV：判为正常的图片中真正正常的比例；在漏检敏感场景中有业务意义。

### 2.2 框级指标

- Recall@IoU0.3/0.5：预测框与任一真实框达到指定 IoU 时算命中。
- mAP50、mAP50-95：衡量框位置与类别准确性。
- 本项目对框位置要求不高，因此模型选择主要看图像级 Recall 与 FPR，框级指标用于解释和诊断。
- 对 Missing Hole 的单类、双类、三类检测器，主要图像级 Recall 使用 class-agnostic 口径：只要在缺陷图上输出任意缺陷框就算识别成功，不要求位置子类预测正确。

## 3. 共同实验规范

### 3.1 数据隔离

- V3/V4 将 343 张数据按近重复组拆分，使用 dHash、文件序号和图像相似性控制泄漏。
- Missing Hole V1 使用 SHA256、dHash、邻近序号、宽高比和灰度相关性建立 270 个组，同组不跨 train/val。
- 测试集不用于训练、温度校准、融合权重或阈值选择。
- V5 保留原 train/val 归属，随后增加一次锁定独立 test；其 test 与 train/val 无 SHA256 完全重复，但存在 75 对 dHash 距离不超过 2 的提示项，需结合图像复核。

### 3.2 训练硬件

- GPU：NVIDIA GeForce RTX 4060 Laptop GPU，约 8 GB 显存。
- 单卡串行训练，CUDA 与 AMP 启用。
- 图片尽量使用 RAM cache，DataLoader 使用 4 至 8 workers。
- OOM 时自动减半 batch；1280 输入在 Windows 多进程异常时降低 workers 后重试。
- Missing Hole V1 监控 1735 个采样点：平均 GPU 利用率 83.9%，峰值 100%，显存峰值 5882 MiB，最高温度 80 C。

### 3.3 共同训练原则

- 检测模型从官方 `yolo26n.pt` 初始化，分类模型从 ImageNet 或官方 `yolo26n-cls.pt` 初始化。
- 主要优化器为 AdamW。
- 快速候选通常训练 25 至 35 epochs，优秀候选训练 80 至 120 epochs并早停。
- 增强以不裁掉微小缺陷为原则：关闭随机裁剪、MixUp、CutMix；检测器通常关闭 Mosaic。
- 阈值均在验证集扫描，先满足 FPR 上限，再最大化 Recall。
- 分类概率使用温度缩放；多模型尝试均值、最大值、加权平均或 OR 类融合。

## 4. V3：高召回判定器加定位器

### 4.1 目标

V3 首次把“是否剔除”与“缺陷在哪里”拆开：

1. 图像级高召回判定器输出 normal、scratch、missing_tooth。
2. scratch 和 missing_tooth 使用独立定位器提供解释框。
3. 目标为两类图像级 Recall 均不低于 0.90，正常 FPR 不高于 0.10；定位模型在 Precision 不低于 0.50 后追求 Recall 不低于 0.70。

### 4.2 数据

| 集合 | scratch | missing_tooth | normal | 合计 |
| --- | ---: | ---: | ---: | ---: |
| train | 56 | 95 | 92 | 243 |
| val | 12 | 18 | 20 | 50 |
| test | 11 | 19 | 20 | 50 |

- 原始总量 343 张，建立 159 个近重复组，最大组 41 张。
- dHash 距离不超过 2 的跨集合泄漏为 0。
- 生成 50 张训练/验证难例复核清单，测试图不进入难例选择。

### 4.3 判定器流程

- YOLO26n-cls：320 输入、60 epochs、AdamW、无随机缩放和擦除，轻量旋转/翻转/颜色增强。
- ResNet18：ImageNet 预训练、AdamW `3e-4`、weight decay `5e-4`、batch 32、AMP。
- 正常特征距离异常检测：使用 ResNet 特征建立正常样本 embedding bank，以特征距离产生异常分数。
- 候选融合：YOLO 单独、ResNet 单独、双分类器、分类器加异常分数、分类器加异常分数加检测器。
- 验证集最终选择 YOLO26n-cls 单独作为 gate；阈值 scratch `0.85`、missing_tooth `0.65`。

### 4.4 定位器候选

所有快速定位候选使用 960 输入、25 epochs、AdamW、无 Mosaic；standard batch 16、P2 batch 8。完整模型训练 90 epochs。

| 候选 | 任务 | 结构/表示 | 验证 Recall | Precision | 结论 |
| --- | --- | --- | ---: | ---: | --- |
| p_s_standard_original | scratch | standard/RGB | 0.059 | 1.000 | scratch 候选中入选 |
| p_s_p2_original | scratch | P2/RGB | 0.059 | 0.174 | Precision 不合格 |
| p_s_p2_clahe | scratch | P2/CLAHE | 0.059 | 0.810 | 未优于 standard |
| p_s_p2_gray | scratch | P2/灰度 | 0.118 | 0.023 | 误报严重 |
| p_m_standard_original | missing | standard/RGB | 0.412 | 0.636 | missing 候选中入选 |
| p_m_p2_original | missing | P2/RGB | 0.103 | 0.500 | 明显下降 |
| p_m_p2_clahe | missing | P2/CLAHE | 0.221 | 0.500 | 未优于 standard |
| p_joint_standard_original | 联合 | standard/RGB | scratch 0.118；missing 0.368 | scratch P 0.191；missing P 0.540 | 联合模型未入选 |
| f_scratch_standard_original_seed42 | scratch | standard/RGB，90 epochs | 0.118 | 0.783 | 验证仍弱 |
| f_missing_tooth_standard_original_seed42 | missing | standard/RGB，90 epochs | 0.471 | 0.525 | 较 scratch 更可学 |

### 4.5 锁定测试结果

图像级 gate：

| 类别 | Precision | Recall | F1 | TP/FP/FN |
| --- | ---: | ---: | ---: | ---: |
| scratch | 1.000 | 0.364 | 0.533 | 4/0/7 |
| missing_tooth | 0.750 | 0.789 | 0.769 | 15/5/4 |

系统正常 FPR 为 0.150。

框级定位：

| 定位器 | Precision | Recall | mAP50 | mAP50-95 | TP/FP/FN |
| --- | ---: | ---: | ---: | ---: | ---: |
| scratch | 0.000 | 0.000 | 0.000 | 0.000 | 0/6/19 |
| missing_tooth | 0.781 | 0.481 | 0.445 | 0.219 | 25/7/27 |

分视角中，missing_tooth 侧视框级 Recall 为 0.722、Precision 为 0.867；oblique Recall 仅 0.238。V3 证明判定与定位分工合理，但旧 scratch 数据无法支持跨组泛化。

## 5. V4：任意缺陷二分类

### 5.1 目标与数据

V4 放弃缺陷类型和位置，只输出 `normal` 或 `defect`。scratch 与 missing_tooth 合并为 defect，目标是在 FPR 不超过 0.30 时达到 Recall 不低于 0.95。

| 集合 | defect | normal | 合计 |
| --- | ---: | ---: | ---: |
| train | 151 | 92 | 243 |
| val | 30 | 20 | 50 |
| test | 30 | 20 | 50 |

拆分沿用 159 个近重复组，跨集合 dHash 距离不超过 2 的泄漏为 0。

### 5.2 数据增强和损失

- 轻量亮度、对比度、Gamma、噪声、模糊、JPEG 压缩、翻转、90 度旋转、概率性 CLAHE。
- 不使用随机裁剪、MixUp、CutMix 或会裁掉缺陷的缩放。
- 自定义分类器使用 AdamW `3e-4`、weight decay `5e-4`、类别/视角均衡采样和缺陷权重。
- 384 输入 batch 24，512 输入 batch 12；YOLO-cls 分别为 32/16。
- 比较原图与四路 TTA，之后执行温度缩放与验证阈值扫描。

### 5.3 第一阶段 9 个基线候选

| 候选 | 输入/权重 | 验证 Recall | FPR | AUPRC |
| --- | --- | ---: | ---: | ---: |
| YOLO-cls | 384/w1 | 0.833 | 0.300 | 0.769 |
| YOLO-cls | 512/w2 | 0.667 | 0.300 | 0.818 |
| YOLO-cls | 512/w4 | 0.600 | 0.300 | 0.677 |
| ResNet18 | 384/w1 | 0.867 | 0.300 | 0.886 |
| ResNet18 | 384/w2 | 0.800 | 0.300 | 0.835 |
| ResNet18 | 512/w4 | 0.900 | 0.300 | 0.853 |
| EfficientNet-B0 | 384/w1 | 0.867 | 0.300 | 0.838 |
| EfficientNet-B0 | 384/w2 | 0.867 | 0.300 | 0.858 |
| EfficientNet-B0 | 512/w4 | 0.867 | 0.300 | 0.862 |

基线最终选中 ResNet18 512、缺陷权重 4、四路 TTA。其测试结果为 Recall 0.567、Precision 0.739、FPR 0.300。

### 5.4 扩展候选与纹理实验

在基线后增加 9 个中等长度候选和 2 个 120 epochs 完整候选：

| 组别 | 配置 | 验证结果概况 |
| --- | --- | --- |
| 多随机种子 | YOLO-cls 384 seed 17/73，50 epochs | 最好 Recall 0.833，FPR 0.25 |
| 多随机种子 | ResNet18 384 seed 17/73，60 epochs | 最好 Recall 0.900，FPR 0.25 |
| 多随机种子 | EfficientNet-B0 384 seed 17/73，60 epochs | 最好 Recall 0.900，FPR 0.30 |
| 纹理三通道 | 灰度 + CLAHE + Laplacian，ResNet18 384/512，80 epochs | 最好 Recall 0.900，FPR 0.30，未形成稳定优势 |
| 完整训练 | ResNet18 384 seed 73，120 epochs | 验证 Recall 0.867，FPR 0.30 |
| 完整纹理训练 | Texture ResNet18 384 seed 73，120 epochs | 验证 Recall 0.867，FPR 0.30 |

共记录 20 个单模型实验。延长单模型在测试上 Recall 0.467、Precision 0.933、FPR 0.050，说明排序能力较好但验证选择阈值迁移后过于保守。

### 5.5 最终融合

融合成员：

1. ResNet18 384 长训，TTA，温度 1.275。
2. YOLO26n-cls 384 seed 17，TTA，温度 2.9。
3. ResNet18 512、缺陷权重 4，TTA，温度 2.025。

融合取三者校准概率最大值。验证集在阈值 `0.702842` 时 Recall 0.933、Precision 0.848、FPR 0.250。

最终留出集：Recall 0.633、Precision 0.731、F1 0.679、FPR 0.350、AUROC 0.707、AUPRC 0.814，TP/FP/TN/FN 为 19/7/13/11。分组 Recall 为 scratch 0.364、missing_tooth 0.789、face 0.556、oblique 0.615、side 0.750。

注意：V4 扩展方向参考过第一次测试结果，因此该 50 张留出集应视为历史评估，而不是完全未查看的最终盲测。

## 6. V5：重新标注后的 Scratch 高召回专项模型

### 6.1 数据准备

- 从原 `images/train`、`images/val` 补齐 16 张有 XML 但 scratch 目录缺图的图片。
- Pascal VOC XML 转为单类 YOLO：`0: scratch`。
- 无 XML 图片按已确认假设视为 normal，并生成空 TXT 标签。
- 原 XML 和原图不覆盖，派生数据写入 `dataset_defects/scratch_v5`。

| 集合 | scratch | normal | 合计 |
| --- | ---: | ---: | ---: |
| train | 119 | 245 | 364 |
| val | 43 | 107 | 150 |
| 合计 | 162 | 352 | 514 |

共 373 个合法 scratch 框；图片、标签、类别与归一化坐标预检通过。

### 6.2 候选与配置

分类器使用 ImageNet 预训练、AdamW `3e-4`、weight decay `5e-4`、CosineAnnealingLR、Focal BCE `gamma=1.5`、按类别和视角均衡采样。384 batch 24、512 batch 12。

检测器使用官方 YOLO26n 权重、960 输入、AdamW `8e-4`、无 Mosaic/MixUp/CutMix、轻量平移缩放和颜色增强；standard batch 12、P2 batch 6。

| 候选 | 类型 | 验证 Recall | Precision | FPR | AUROC |
| --- | --- | ---: | ---: | ---: | ---: |
| ResNet18 384 w1 | 快速分类 | 0.930 | 0.727 | 0.140 | 0.941 |
| ResNet18 512 w2 | 快速分类 | 0.930 | 0.656 | 0.196 | 0.914 |
| EfficientNet-B0 384 w1 | 快速分类 | 0.930 | 0.690 | 0.168 | 0.941 |
| EfficientNet-B0 512 w2 | 快速分类 | 0.860 | 0.661 | 0.178 | 0.913 |
| YOLO26n-cls 384 w1 | 快速分类 | 0.744 | 0.604 | 0.196 | 0.865 |
| YOLO26n-cls 512 w2 | 快速分类 | 0.698 | 0.588 | 0.196 | 0.854 |
| standard YOLO26n 960 | 快速检测 | 0.884 | 0.644 | 0.196 | 0.913 |
| YOLO26-P2 960 | 快速检测 | 0.884 | 0.667 | 0.178 | 0.929 |
| ResNet18 384 | 完整分类 | 0.930 | 0.690 | 0.168 | 0.928 |
| EfficientNet-B0 384 | 完整分类 | 0.953 | 0.759 | 0.121 | 0.950 |

训练过程中从训练集 FN/FP 构造 hard-case 权重：漏检 scratch 最多 3 倍，误报 normal 最多 2 倍。只用于 train，不读取测试误判。

### 6.3 最终融合配置

- 分类器 1：EfficientNet-B0 384，温度 0.7。
- 分类器 2：ResNet18 384，温度 2.05。
- 辅助检测器：YOLO26-P2 960，温度 2.125，NMS IoU 0.7。
- 两个分类器先取均值。
- 最终分数 = `0.25 × 分类器均值 + 0.75 × 检测器概率`。
- 默认阈值 `0.3002736103`。

### 6.4 验证与独立测试

| 数据 | Recall | Precision | F1 | FPR | AUROC | AUPRC | TP/FP/TN/FN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| val | 0.977 | 0.824 | 0.894 | 0.084 | 0.972 | 0.937 | 42/9/98/1 |
| 锁定 test_scratch | 0.806 | 0.556 | 0.658 | 0.168 | 0.883 | 0.812 | 25/20/99/6 |

测试集 150 张，其中 scratch 31、normal 119。6 张 FN 主要是正视/斜视、小面积、低对比 scratch；20 张 FP 主要是侧齿高光和正常加工纹。激进阈值 `0.203814` 可将测试 Recall 提到 0.935，但 FPR 达 0.588，不适合作为默认生产阈值。

## 7. Missing Hole V1：位置标签、difficult 与融合实验

### 7.1 任务和数据

源目录沿用 `*_missing_tooth`，模型语义统一为 `missing_hole`。

| 集合 | 图片 | 缺陷图 | 无 missing_hole | 框 | difficult 框 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 原训练池 | 496 | 173 | 323 | 614 | 25 |
| 派生 train | 397 | - | - | - | - |
| 派生 val | 99 | 34 | 65 | 116 | 3 张含 difficult |
| 锁定 test | 150 | 44 | 106 | 168 | 6 |

- 固定种子 `20260913`。
- 218 个 XML 的尺寸、类别与坐标通过校验。
- `test_047.xml` 无对象，按无 missing_hole 处理。
- 只含 difficult 框的 6 张训练图在 exclude 策略中整图排除，不生成错误空标签。

### 7.2 六套标签

| 方案 | 类别 | difficult 版本 |
| --- | --- | --- |
| 三类 | bottom、oblique、side | include / exclude |
| 两类 | bottom_oblique、side | include / exclude |
| 单类 | missing_hole | include / exclude |

test 的主要图像级指标不要求类别预测正确；类别标签用于给模型提供结构监督并做位置子组诊断。

### 7.3 十二组检测初筛

统一配置：官方 YOLO26n 初始化、960 输入、35 epochs、AdamW `7e-4`、weight decay `5e-4`、Mosaic/MixUp/Copy-Paste 关闭、轻量旋转平移缩放与颜色增强。standard 与 P2 均串行训练。

| 类别 | difficult | 架构 | Recall | Precision | FPR | AUPRC |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| 单类 | exclude | standard | 0.971 | 0.846 | 0.092 | 0.945 |
| 单类 | exclude | P2 | 0.971 | 0.717 | 0.200 | 0.942 |
| 单类 | include | standard | 0.971 | 0.733 | 0.185 | 0.966 |
| 单类 | include | P2 | 0.882 | 0.790 | 0.123 | 0.945 |
| 两类 | exclude | standard | 0.941 | 0.865 | 0.077 | 0.957 |
| 两类 | exclude | P2 | 0.882 | 0.833 | 0.092 | 0.921 |
| 两类 | include | standard | 0.912 | 0.816 | 0.108 | 0.909 |
| 两类 | include | P2 | 0.941 | 0.821 | 0.108 | 0.922 |
| 三类 | exclude | standard | 0.912 | 0.838 | 0.092 | 0.932 |
| 三类 | exclude | P2 | 0.912 | 0.756 | 0.154 | 0.907 |
| 三类 | include | standard | 0.912 | 0.795 | 0.123 | 0.951 |
| 三类 | include | P2 | 0.941 | 0.821 | 0.108 | 0.947 |

结论：业务只关心有无 missing_hole 时，单类监督最好；三类会分散当前有限数据的正样本。P2 没有超过 standard。

### 7.4 十二组分类初筛

比较 ResNet18、EfficientNet-B0、YOLO26n-cls，384/512 输入，include/exclude difficult，共 12 组、30 epochs。分类器使用 Focal BCE、类别均衡采样、AdamW、轻量非裁剪增强，并在 val 比较 none/flip/rot90 TTA和温度缩放。

- ResNet18 快速候选 Recall 0.912 至 0.971。
- EfficientNet-B0 快速候选 Recall 0.941 至 0.971。
- YOLO26n-cls 快速候选 Recall 0.676 至 0.853，整体较弱。

### 7.5 完整、确认、分辨率与强化实验

| 实验 | 配置 | 验证 Recall | Precision | FPR | 结论 |
| --- | --- | ---: | ---: | ---: | --- |
| 完整分类 | EfficientNet-B0 512 exclude，100 epochs | 1.000 | 0.850 | 0.092 | 最佳分类器 |
| 完整分类 | ResNet18 384 include，100 epochs | 1.000 | 0.810 | 0.123 | 第二分类器 |
| 第二种子确认 | EfficientNet-B0 512 exclude，seed 20260914 | 1.000 | 0.810 | 0.123 | Recall 稳定，FPR 有波动 |
| 完整检测 | 三类 include P2 960，100 epochs | 0.941 | 0.842 | 约 0.092 | 未胜过单类 |
| 完整检测 | 两类 exclude standard 960，100 epochs | 0.912 | 0.838 | 约 0.092 | 未胜过单类 |
| 完整检测 | 单类 exclude standard 960，100 epochs | 0.971 | 0.846 | 0.092 | 最佳检测配置保持稳定 |
| 高分辨率 | 三类 include P2 1280 | 0.941 | 0.727 | 0.185 | 无收益 |
| 高分辨率 | 两类 exclude standard 1280 | 0.941 | 0.727 | 0.185 | Recall 小升但误报翻倍 |
| 高分辨率 | 单类 exclude standard 1280 | 0.882 | 0.750 | 0.154 | 明显变差 |
| 强化 | 单类 exclude standard 960 + CLAHE/难例重采样 | 0.941 | 0.821 | 0.108 | 低于基础模型 |

Missing Hole 专项共记录 34 个实验：24 个快速候选、5 个 960 完整候选（3 个检测器、2 个分类器）、3 个 1280 完整对照、1 个第二种子确认和 1 个强化实验。另有 5 个 scratch + missing_hole 统一模型候选，因此本轮合计完成 39 个训练实验。

### 7.6 最终融合

- EfficientNet-B0 512 exclude difficult，温度 1.0。
- ResNet18 384 include difficult，温度 2.375。
- 单类 standard YOLO26n 960 exclude difficult，温度 1.85。
- 分类器取均值，再与检测器按 0.5/0.5 加权。
- 默认阈值 `0.3413327979`。

验证集：Recall 1.000、Precision 0.895、FPR 0.062，TP/FP/TN/FN 为 34/4/61/0。

### 7.7 锁定 test 与 difficult 结果

| 统计口径 | Recall | Precision | F1 | FPR | TP/FP/TN/FN |
| --- | ---: | ---: | ---: | ---: | ---: |
| 包含 difficult | 0.818 | 0.900 | 0.857 | 0.038 | 36/4/102/8 |
| 忽略 difficult | 0.814 | 0.897 | 0.854 | 0.038 | 35/4/102/8 |
| 纯易样本 | 0.821 | 0.889 | 0.853 | 0.038 | 32/4/102/7 |

5 张图片含 difficult 框，命中 4 张，difficult 图像级 Recall 为 0.80，唯一漏检为 `test_140`。三种统计口径差异很小，difficult 不是主要瓶颈。

位置子组：bottom Recall 0.917，oblique 0.588，side 1.000。框级 class-agnostic Recall@IoU0.3/0.5 为 0.601/0.554；class-aware mAP50/mAP50-95 为 0.501/0.209。

### 7.8 Scratch 合并与统一模型

统一训练集保留 364 张双缺陷监督完整图片，并加入 73 张额外明确 missing_hole 正样本，共 437 张；排除 59 张 scratch 状态未知的负候选。

| 统一候选 | 类型 | 验证 Recall | Precision | FPR |
| --- | --- | ---: | ---: | ---: |
| ResNet18 512 | 分类 | 0.887 | 0.922 | 0.167 |
| EfficientNet-B0 512 | 分类 | 0.943 | 0.926 | 0.167 |
| YOLO26n-cls 512 | 分类 | 0.717 | 0.905 | 0.167 |
| YOLO26-P2 960 单类 any_defect | 检测 | 0.724 | 0.840 | 0.167 |
| YOLO26-P2 960 双类 | 检测 | 0.655 | 0.826 | 0.167 |

锁定 test：

| 生产方案 | 任意缺陷 Recall | Precision | FPR | TP/FP/TN/FN |
| --- | ---: | ---: | ---: | ---: |
| Scratch V5 + Missing Hole V1 专项 OR | 0.887 | 0.778 | 0.228 | 63/18/61/8 |
| 统一 EfficientNet-B0 单模型 | 0.761 | 0.621 | 0.418 | 54/33/46/17 |

当前推荐专项 OR。统一模型权重约 15.6 MB，双专项部署约 130 MB；前者轻但精度损失明显。

## 8. 四代实验横向结论

### 8.1 被证实有效的方法

1. 按近重复组拆分数据，暴露了此前被相邻帧掩盖的真实泛化问题。
2. 分类器与检测器融合在验证集上通常优于单分支，V5 与 Missing Hole V1 均采用该路线。
3. 专项模型拆分比统一模型更适合大小、纹理和视角差异明显的两类缺陷。
4. 使用正常难负样本、关闭会裁掉缺陷的增强、温度校准和 FPR 约束阈值，对生产口径有实际价值。
5. Missing Hole 单类检测比位置三分类检测更符合“识别到即可”的业务目标。

### 8.2 无稳定收益或已失败的方法

| 方法 | 实际观察 |
| --- | --- |
| P2 一律替代 standard | V3 scratch/missing 多数变差；Missing Hole 最佳为 standard；仅 V5 辅助检测器选择 P2 |
| 960 提升到 1280 | Missing Hole 三组对照均无稳定收益，单类显著下降 |
| CLAHE | V3 与 Missing Hole 均未形成稳定优势；可能放大反光和加工纹 |
| 灰度或纹理三通道 | V3 灰度误报严重；V4 纹理模型没有超过 RGB 基线 |
| 普通滑窗局部检测 | V2 scratch Recall 从整图 0.577 降到 0.538 |
| 单纯延长训练 | V4 与 Missing Hole 未解决跨拍摄组分布差异 |
| 统一任意缺陷模型 | test Recall 0.761、FPR 0.418，弱于专项 OR |
| 仅调低阈值追 Recall | V5 激进阈值 Recall 0.935，但 FPR 0.588，无法生产使用 |

## 9. 对 `优化方案.md` 的逐项核对

为避免“尝试过几种”因拆分粒度不同而产生歧义，本报告按 27 个主要技术方向归并统计：

- 已完整尝试：11 项。
- 部分尝试：4 项。
- 尚未尝试：12 项。

### 9.1 已完整尝试的 11 项

| 优化方向 | 在哪里尝试 | 效果 |
| --- | --- | --- |
| 相似样本分组、train/val/test 隔离 | V3、V4、Missing Hole V1 | 成功清零指定近重复跨集合泄漏，也暴露出真实测试下降 |
| 非裁剪型人工增强 | V3/V4/V5/Missing Hole | 旋转、翻转、亮度、对比度、Gamma、噪声、模糊、JPEG 等均已使用；有助于稳健性，但不能单独解决低可见缺陷 |
| 正常困难负样本 | V2、V5、Missing Hole | 纳入反光、加工纹和另一缺陷类型；降低部分误报，但测试仍有高光误报 |
| 高分辨率训练 | V2 的 960/1280、Missing Hole 的 960/1280，分类 384/512 | 1280 无稳定收益且更慢；512 也不总优于 384 |
| hard-case 重采样 | V3、V5、Missing Hole | V5 用于完整训练；Missing Hole 的 CLAHE + hard-case 强化反而由 R 0.971 降到 0.941 |
| 输入尺寸对比 | V4/V5 分类 384/512，检测 960/1280 | 找到了任务相关最佳尺寸，但没有“尺寸越大越好” |
| epoch 与早停 | 25/30/35 快筛，80/90/100/120 长训 | 已系统比较；更长训练未解决数据分布问题 |
| 官方预训练 | YOLO 官方检测/分类权重，ImageNet ResNet/EfficientNet | 相比从零训练更合理，所有最终模型均使用预训练 |
| 置信度阈值扫描 | V2-V5、Missing Hole | 成功按 FPR 约束选择工作点，并保存激进阈值 |
| P2 检测头 | V3、V5、Missing Hole | 结果混合；V5 选中 P2，Missing Hole 由 standard 获胜，不能默认 P2 必胜 |
| 模型拆分 | V2、V3、V5 + Missing Hole，另与统一模型比较 | 明确有效；专项 OR test Recall 0.887，高于统一模型 0.761 |

### 9.2 部分尝试的 4 项

| 优化方向 | 已做部分 | 尚缺部分 |
| --- | --- | --- |
| 两次检测/ROI 裁切 | 第一阶段齿轮模型已检测并裁切 ROI；历史上做过局部滑窗 | 未做严格的“原图直接训练 vs 同批图先归一化 ROI”单变量消融，也未做多实例分类式二次检查 |
| 严格单变量消融 | standard/P2、384/512、960/1280、include/exclude difficult 等有公平对照 | 多项扩展实验同时改变种子、训练轮数或表示，尚未形成完整正交实验表 |
| batch 搜索 | 根据输入尺寸设置 batch，并做 OOM 自动减半 | 未把 batch 当作精度变量系统扫描；当前主要是显存适配 |
| 几何归一化 | 已裁切齿轮 ROI，部分数据主体尺寸较统一 | 尚未完整实现中心定位、统一直径、旋转校正、齿圈裁剪和极坐标展开 |

### 9.3 尚未尝试的 12 项

| 优化方向 | 状态 | 建议优先级 |
| --- | --- | --- |
| 工业相机、上下双镜头、亚克力/背光、固定传送带位置 | 未做软件实验，需要改采集硬件 | 最高，尤其解决 bottom/oblique 不可见问题 |
| 专门模拟镜面反光 | 仅有亮度/对比度增强，没有物理合理的高光合成 | 中；更推荐先采真实高光负样本 |
| 学习率系统扫描 | 各代使用固定 LR，没有独立 lr 消融 | 中低，数据可见性改善后再做 |
| SGD 与 AdamW 公平比较 | 所有主要实验使用 AdamW | 中低 |
| 相似工业缺陷数据预训练 | 只使用通用官方/ImageNet 预训练 | 中；前提是找到域相近且标签可信的数据 |
| NMS IoU 系统扫描 | 多数固定为 0.7，仅扫描置信度 | 低；本项目图像级判定受其影响有限 |
| 删除 P5 / 修改 P5 融合 | 未改模型主干/Neck | 低至中，需要部署速度或结构研究时开展 |
| 加深 P2/P3、增加通道、注意力机制 | 未实现定制 Neck 与 C3k2-attn 消融 | 中，需在新数据和固定基线后逐项验证 |
| 轻量化 P2 Detect Head H0/H1/H2 | 未实现 | 中低，主要用于 Jetson 性能优化 |
| 知识蒸馏 | 未实现教师-学生训练 | 中，先让教师模型在新盲测上达标 |
| INT8/FP16 部署、结构化剪枝 | 训练用了 AMP，但没有 TensorRT FP16/INT8 精度与速度评估，也未剪枝 | 后置，精度达标后进行 |
| trtexec、零拷贝、GPU 预处理和自定义 CUDA | 未做部署端基准 | 后置，主项目迁移后按真实链路测试 |

## 10. 下一阶段推荐顺序

1. 优先改采集：为每颗齿轮提供上/下或多角度图，增加低角度环形光与背光轮廓，使 bottom/oblique 缺口在输入中真正可见。
2. 按“实体齿轮 + 拍摄批次”分组采集新 train/val，并保留全新批次作为一次性 blind test。
3. Scratch 增加低对比小划痕正样本，以及侧齿高光、圆周加工纹、灰尘等同角度正常负样本。
4. 在第一阶段齿轮 ROI 上做几何归一化，再开展“整图 + 2×2/3×3 重叠局部块”的多实例分类，而不是继续普通框检测滑窗。
5. Missing Hole 对 oblique 尝试齿圈极坐标展开、轮廓周期异常或多视角 OR；单帧中不可见的缺陷不能靠更大模型凭空恢复。
6. 新数据固定后，再做严格单变量实验：baseline、ROI、hard-case、P2、注意力、学习率、优化器。
7. 精度达标后再进入 Jetson：先测 PyTorch/ONNX/TensorRT FP16，速度仍不足再考虑 INT8、结构化剪枝和知识蒸馏。

## 11. 关键产物索引

| 内容 | 路径 |
| --- | --- |
| V3 报告 | `outputs/defect_search_v3/README.md`、`final_report.json` |
| V3 排行榜 | `outputs/defect_search_v3/leaderboard.csv` |
| V4 报告 | `outputs/binary_defect_v4/README.md`、`final_report.json` |
| V4 排行榜 | `outputs/binary_defect_v4/leaderboard.csv` |
| V5 迁移说明 | `docs/Scratch_V5_迁移与集成说明.md` |
| V5 独立测试 | `outputs/scratch_v5/test_scratch/test_report.json` |
| Missing Hole 最终报告 | `docs/missing_hole_v1/FINAL_REPORT.md` |
| Missing Hole 全部专项实验 | `docs/missing_hole_v1/experiments/` |
| Missing Hole 排行榜 | `outputs/missing_hole_v1/leaderboard.csv` |
| Missing Hole 锁定测试 | `outputs/missing_hole_v1/test/test_report.json` |
| 专项统一推理 | `infer_gear_defects.py` |
| Scratch 推理配置 | `outputs/scratch_v5/inference_config.json` |
| Missing Hole 推理配置 | `outputs/missing_hole_v1/inference_config.json` |

## 12. 最终结论

当前最可靠的技术路线不是继续堆叠单模型复杂度，而是：稳定采集和可见性、按实体/批次防泄漏拆分、scratch 与 missing_hole 专项建模、验证集校准阈值、生产端 OR 合并。现有专项 OR 已取得 0.887 的任意缺陷 Recall，但 FPR 0.228，仍未达到 Recall 0.95 且 FPR 不超过 0.20 的目标。

下一轮最值得投入的不是 1280、更多 epoch 或重复 CLAHE，而是新增独立 oblique 缺口与低对比 scratch 数据、真实高光负样本、多视角采集和 ROI 几何归一化。模型结构定制与 Jetson 轻量化应在新数据基线稳定后再进入。
