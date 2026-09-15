# Missing Hole V1 最终实验报告

## 1. 结论

本轮完成了数据转换、无泄漏拆分、34 个专项实验、统一缺陷模型实验、第二随机种子确认和一次锁定 test 评估。

- Missing Hole 专项融合在验证集达到 Recall `1.0000`、Precision `0.8947`、FPR `0.0615`。
- 在独立 test 上，专项融合 Recall 为 `0.8182`、Precision 为 `0.9000`、FPR 为 `0.0377`。
- 与 Scratch V5 按 OR 规则联合后，missing-hole 缺陷被任一专项模型剔除的 Recall 为 `0.9318`。
- 双专项系统对任意缺陷的 Recall 为 `0.8873`、FPR 为 `0.2278`。
- 精简单分类模型在 test 上的任意缺陷 Recall 为 `0.7606`、FPR 为 `0.4177`，不建议替代双专项系统。
- 目标 Recall >= `0.95` 且 FPR <= `0.20` 未达到。主要瓶颈是 `oblique`，test Recall 仅 `0.5882`。

独立 test 已于 `2026-09-13 17:07:01` 一次性评估并锁定。后续不得使用这 150 张图片重新选择模型、融合方式或阈值。

## 2. 数据与隔离

| 集合 | 图片 | 缺陷图 | 无 missing_hole | 框 | difficult 框 |
|---|---:|---:|---:|---:|---:|
| 原训练池 | 496 | 173 | 323 | 614 | 25 |
| 派生 train | 397 | - | - | - | - |
| 派生 val | 99 | 34 | 65 | 116 | 3 张含 difficult |
| 锁定 test | 150 | 44 | 106 | 168 | 6 |

固定种子为 `20260913`。共建立 270 个近重复组，同组不跨 train/val。原 train 与 test 无 SHA256 重复或 dHash 距离 <=2 的跨集合近重复。

六套基础 YOLO 数据完整生成：三类、两类、单类分别搭配 include/exclude difficult。仅含 difficult 框的 6 张训练图片在 exclude 策略中整图排除，没有被错误转换成正常负样本。

## 3. 十二组检测初筛

以下均为 960 输入、35 epochs，指标按验证集 FPR <=20% 后最大化图像级 Recall。

| 类别方案 | difficult | 架构 | Recall | Precision | FPR | AUPRC |
|---|---|---|---:|---:|---:|---:|
| 单类 | exclude | standard | **0.9706** | **0.8462** | **0.0923** | 0.9447 |
| 单类 | exclude | P2 | 0.9706 | 0.7174 | 0.2000 | 0.9415 |
| 单类 | include | standard | 0.9706 | 0.7333 | 0.1846 | **0.9658** |
| 单类 | include | P2 | 0.8824 | 0.7895 | 0.1231 | 0.9450 |
| 两类 | exclude | standard | 0.9412 | 0.8649 | 0.0769 | 0.9571 |
| 两类 | exclude | P2 | 0.8824 | 0.8333 | 0.0923 | 0.9205 |
| 两类 | include | standard | 0.9118 | 0.8158 | 0.1077 | 0.9091 |
| 两类 | include | P2 | 0.9412 | 0.8205 | 0.1077 | 0.9220 |
| 三类 | exclude | standard | 0.9118 | 0.8378 | 0.0923 | 0.9321 |
| 三类 | exclude | P2 | 0.9118 | 0.7561 | 0.1538 | 0.9073 |
| 三类 | include | standard | 0.9118 | 0.7949 | 0.1231 | 0.9506 |
| 三类 | include | P2 | 0.9412 | 0.8205 | 0.1077 | 0.9467 |

结论：只关心“是否有缺口”时，单类标签最好；两类标签适合保留 side 与其他位置的诊断差异；三类标签在当前数据量下分散了监督信号。

## 4. 分类、分辨率与难例实验

分类器精训结果：

| 模型 | difficult | Recall | Precision | FPR | AUPRC |
|---|---|---:|---:|---:|---:|
| EfficientNet-B0 512 | exclude | **1.0000** | **0.8500** | **0.0923** | 0.9247 |
| ResNet18 384 | include | 1.0000 | 0.8095 | 0.1231 | 0.8911 |
| EfficientNet-B0 512 第二种子 | exclude | 1.0000 | 0.8095 | 0.1231 | 0.8609 |

YOLO26n-cls 的快速候选 Recall 为 `0.6765` 至 `0.8529`，明显弱于 EfficientNet-B0 和 ResNet18。

1280 输入没有带来收益：

| 方案 | 960 Recall/FPR | 1280 Recall/FPR |
|---|---:|---:|
| 三类 include P2 | 0.9412 / 0.0923 | 0.9412 / 0.1846 |
| 两类 exclude standard | 0.9118 / 0.0923 | 0.9412 / 0.1846 |
| 单类 exclude standard | 0.9706 / 0.0923 | 0.8824 / 0.1538 |

CLAHE 加难例重采样也未超过基础单类检测器：强化版 Recall `0.9412`、FPR `0.1077`。这说明当前误差主要不是分辨率或训练轮数不足，而是 oblique 的可见特征和训练/test 分布差异。

## 5. Difficult 结论

- 验证集最好的分类器和检测器都来自 `exclude_difficult`。
- test 中 5 张图片含 difficult 框，命中 4 张，图像级 difficult Recall 为 `0.8000`。
- 唯一 difficult 漏检为 `test_140`。
- 包含 difficult 的总体 Recall 为 `0.8182`；标准忽略 difficult 为 `0.8140`；纯易样本为 `0.8205`。
- 三种口径差异很小，difficult 不是总体低召回的主要来源。

## 6. 锁定 Test 结果

| 统计口径 | Recall | Precision | F1 | FPR | TP/FP/TN/FN |
|---|---:|---:|---:|---:|---:|
| 包含 difficult | 0.8182 | 0.9000 | 0.8571 | 0.0377 | 36/4/102/8 |
| 忽略 difficult | 0.8140 | 0.8974 | 0.8537 | 0.0377 | 35/4/102/8 |
| 纯易样本 | 0.8205 | 0.8889 | 0.8533 | 0.0377 | 32/4/102/7 |

位置分组：

| 位置 | 图片 | Recall |
|---|---:|---:|
| bottom | 12 | 0.9167 |
| oblique | 17 | **0.5882** |
| side | 20 | 1.0000 |

定位器按低置信度辅助框统计：class-agnostic Recall@IoU0.3 为 `0.6012`，Recall@IoU0.5 为 `0.5536`；忽略 difficult 后分别为 `0.5926` 和 `0.5494`。class-aware mAP50 为 `0.5012`，mAP50-95 为 `0.2087`。框级位置不是生产选择主指标。

## 7. Scratch 合并结果

| 方案 | 任意缺陷 Recall | Precision | FPR | TP/FP/TN/FN |
|---|---:|---:|---:|---:|
| Scratch V5 + Missing Hole V1 专项 OR | **0.8873** | **0.7778** | **0.2278** | 63/18/61/8 |
| 统一 EfficientNet-B0 单模型 | 0.7606 | 0.6207 | 0.4177 | 54/33/46/17 |

双专项 OR 对 scratch Recall 为 `0.8065`，对 missing_hole Recall 为 `0.9318`。统一单模型更小、更简单，但当前泛化明显较差，因此生产推荐保留专项模型。

Missing Hole 专项包包含两个分类器和一个检测器，总权重约 66.5 MB；与 Scratch V5 一起部署约 130 MB。统一单模型约 15.6 MB。若生产延迟敏感，可先运行分类器，只有临界样本再运行检测器，但新门控规则必须在新的验证集上确定。

## 8. 生产配置

Missing Hole 最终融合：

- EfficientNet-B0 512，exclude difficult。
- ResNet18 384，include difficult。
- 单类标准 YOLO26n 960，exclude difficult。
- 两个分类器取均值，再与检测器按 `0.5/0.5` 加权。
- 默认阈值 `0.3413327979`。
- Scratch 与 Missing Hole 任一专项结果过阈值即 `REJECT`。

推理命令：

```powershell
& "F:\Work\VSCode\Projects\DATASET\.venv\Scripts\python.exe" `
  "F:\Work\VSCode\Projects\DATASET\infer_gear_defects.py" `
  "图片或图片目录"
```

正常 `test_001` 和缺陷 `test_009` 的完整推理冒烟测试均通过。

训练全程使用 RTX 4060 Laptop GPU、CUDA、AMP、RAM cache 和最多 8 个数据加载进程。GPU 监控共记录 1735 个采样点，平均计算利用率 `83.9%`、峰值 `100%`，平均显存约 `3957 MiB`、峰值 `5882 MiB`，最高温度 `80 C`。1280 输入在 Windows 多进程加载失败时会自动降低 worker 数后重试。

## 9. 下一轮优化建议

1. 首先补拍和复核 oblique。建议新增至少 100 张独立 oblique 缺陷与 100 张相同角度正常/反光负样本，并按拍摄批次分组。
2. 改善采集可见性。底部斜缺口若肉眼几乎不可见，单帧 RGB 模型没有可靠信息；优先增加低角度环形光、背光轮廓、转台多视角或第二相机。
3. 将一颗齿轮的多角度图片作为一个 group，并在生产上聚合多帧概率。只要任一视角命中即剔除，通常比继续扩大单帧模型更符合召回优先目标。
4. 下一轮用 group-stratified 交叉验证选择结构和阈值，再建立全新盲测集。当前 test 只作为 V1 历史基线。
5. 若继续定位 oblique，可做面向齿圈的极坐标展开，把圆周缺口变成近似水平纹理，再训练小型分类器或 1D 周期异常模型。
6. 不建议继续单纯增加 epochs、切换 1280 或重复 CLAHE；本轮已经完整验证，这三项没有解决泛化瓶颈。

## 10. 产物索引

- `outputs/missing_hole_v1/inference_config.json`：专项固定配置。
- `outputs/missing_hole_v1/final/`：专项最终权重。
- `outputs/missing_hole_v1/leaderboard.csv`：全部专项实验排行榜。
- `outputs/missing_hole_v1/test/test_report.json`：机器可读锁定测试结果。
- `outputs/missing_hole_v1/test/README.md`：简明测试报告。
- `outputs/missing_hole_v1/test/test_predictions.csv`：逐图预测。
- `outputs/missing_hole_v1/test/visualizations/`：代表性可视化。
- `outputs/unified_defect_v1/`：精简单模型及配置。
- `docs/missing_hole_v1/experiments/`：每个实验的独立说明。
