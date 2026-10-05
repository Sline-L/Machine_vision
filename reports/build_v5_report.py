from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "scratch_v5"
RUNS = ROOT / "runs" / "scratch_v5"
DATA = ROOT / "dataset_defects" / "scratch_v5"
REPORT = ROOT / "reports" / "V5实验详细技术报告.md"


def f(value, digits=3):
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}"


def manifest_stats():
    rows = list(csv.DictReader((DATA / "scratch_manifest.csv").open(encoding="utf-8-sig")))
    result = {}
    for split in ("train", "val"):
        items = [r for r in rows if r["split"] == split and r["excluded_from_train"].lower() != "true"]
        labels = Counter(r["label"] for r in items)
        views, label_views = Counter(), Counter()
        for r in items:
            w, h = int(r["width"]), int(r["height"])
            ratio = max(w / h, h / w)
            view = "side" if ratio >= 1.8 else "oblique" if ratio >= 1.25 else "face"
            views[view] += 1
            label_views[(r["label"], view)] += 1
        result[split] = {
            "total": len(items), "labels": labels, "views": views, "label_views": label_views,
            "boxes": sum(int(r["boxes"]) for r in items),
        }
    return result


def custom_summary(name):
    p = RUNS / name / "history.json"
    if not p.exists():
        return {}
    rows = json.loads(p.read_text(encoding="utf-8"))
    best = max(rows, key=lambda r: (r["fpr"] <= 0.2, r["recall"], -r["fpr"], r["precision"]))
    return {
        "actual": len(rows), "best_epoch": best["epoch"], "best_recall": best["recall"],
        "best_fpr": best["fpr"], "best_precision": best["precision"],
        "last_loss": rows[-1]["loss"], "raw_threshold": best["threshold"],
    }


def yolo_summary(name):
    p = RUNS / name / "results.csv"
    if not p.exists():
        return {}
    rows = [{k.strip(): v for k, v in r.items()} for r in csv.DictReader(p.open(encoding="utf-8"))]
    is_detector = "metrics/mAP50(B)" in rows[0]
    if is_detector:
        best = max(rows, key=lambda r: float(r["metrics/mAP50-95(B)"]))
        return {
            "actual": len(rows), "best_epoch": int(float(best["epoch"])),
            "precision": float(best["metrics/precision(B)"]), "recall": float(best["metrics/recall(B)"]),
            "map50": float(best["metrics/mAP50(B)"]), "map5095": float(best["metrics/mAP50-95(B)"]),
            "time": float(rows[-1]["time"]),
        }
    best = max(rows, key=lambda r: float(r["metrics/accuracy_top1"]))
    return {
        "actual": len(rows), "best_epoch": int(float(best["epoch"])),
        "top1": float(best["metrics/accuracy_top1"]), "train_loss": float(best["train/loss"]),
        "val_loss": float(best["val/loss"]), "time": float(rows[-1]["time"]),
    }


def batch_for(row):
    if row["kind"] == "detector":
        return 12 if row["architecture"] == "standard" else 6
    if row["family"] == "yolo_cls":
        return 32 if row["size"] == 384 else 16
    return 24 if row["size"] == 384 else 12


def exp_conclusion(row):
    name = row["name"]
    selected = {
        "f_efficientnet_b0_384_w1_s20260911": "最终分类器 1；在正式单模型中取得最高 AUPRC，并在 FPR≤0.20 时达到 Recall 0.953。",
        "p_resnet18_384_w1": "最终分类器 2；提供与 EfficientNet 不同的残差架构误差模式。",
        "p_detector_p2_960": "最终检测器；图像级排序和 FPR 优于标准检测头，尽管框级精度很低。",
    }
    if name in selected:
        return selected[name]
    if row["kind"] == "detector":
        return "保留了检测结构对照证据，但按图像级主排序未成为最终检测分支。"
    if row["family"] == "yolo_cls":
        return "YOLO 分类分支的图像级 Recall/AUPRC 低于自定义分类器，因此未进入最终分类器集合。"
    if row["stage"] == "full":
        return "完整复训提供长训练预算对照，但未进入最终两分类器组合。"
    if float(row["defect_weight"]) == 2:
        return "512+w2 未优于同架构 384+w1，说明扩大输入与提高正类权重的组合没有稳定收益。"
    return "作为架构和输入设置的候选证据保留，未进入最终融合。"


def experiment_section(index, row):
    p = row["operating_points"]["0.2"]
    summary = yolo_summary(row["name"]) if row.get("family") == "yolo_cls" or row["kind"] == "detector" else custom_summary(row["name"])
    points = []
    for cap in ("0.1", "0.2", "0.3", "0.5"):
        q = row["operating_points"][cap]
        points.append(f"| {cap} | {f(q['threshold'], 9)} | {f(q['recall'])} | {f(q['precision'])} | {f(q['f1'])} | {f(q['fpr'])} | {q['tp']}/{q['fp']}/{q['tn']}/{q['fn']} |")
    if row["kind"] == "detector":
        identity = f"YOLO26 {'标准头' if row['architecture']=='standard' else 'P2 小目标头'}；输入 960；官方 `yolo26n.pt` 初始化；epoch 上限 {row['epochs']}；batch={batch_for(row)}。"
        train_result = (f"训练记录 {summary.get('actual','—')} 行；按 mAP50-95 回看最佳 epoch {summary.get('best_epoch','—')}，"
                        f"框级 P/R/mAP50/mAP50-95={f(summary.get('precision'))}/{f(summary.get('recall'))}/{f(summary.get('map50'))}/{f(summary.get('map5095'))}。")
        boxes = row.get("box_iou_0.3", {})
        extra = f"在图像级运行点对应的原始置信阈值下，IoU=0.3 框级 P/R/F1={f(boxes.get('precision'))}/{f(boxes.get('recall'))}/{f(boxes.get('f1'))}，TP/FP/FN={boxes.get('tp','—')}/{boxes.get('fp','—')}/{boxes.get('fn','—')}。"
    else:
        impl = "训练集正类复制" if row["family"] == "yolo_cls" else "Focal BCE 正类梯度系数"
        identity = (f"{row['family']}；输入 {row['size']}；defect_weight={row['defect_weight']:g}，其实现是{impl}；"
                    f"epoch 上限 {row['epochs']}；batch={batch_for(row)}。")
        if row["family"] == "yolo_cls":
            train_result = (f"实际记录 {summary.get('actual','—')} epochs；最高 top1={f(summary.get('top1'))} 位于 epoch {summary.get('best_epoch','—')}，"
                            f"该轮 train/val loss={f(summary.get('train_loss'))}/{f(summary.get('val_loss'))}。")
        else:
            train_result = (f"实际记录 {summary.get('actual','—')} epochs；按主排序回看最佳 epoch {summary.get('best_epoch','—')}，"
                            f"原始 Recall/FPR/Precision={f(summary.get('best_recall'))}/{f(summary.get('best_fpr'))}/{f(summary.get('best_precision'))}，"
                            f"原始阈值={f(summary.get('raw_threshold'),6)}；末轮 loss={f(summary.get('last_loss'),6)}。")
        extra = f"none 与四路 TTA 比较后选择 `{row['tta']}`。"
    return f"""### 6.{index} {row['name']}

**实验内容与完整差异参数。** 阶段=`{row['stage']}`；类型=`{row['kind']}`；{identity}seed={row['seed']}；其余参数完整继承第 5 章对应模型族公共配置。

**训练、校准与选择。** {train_result}{extra} 温度缩放 T={f(row['temperature'])}。主运行点为 FPR cap=0.20：阈值={f(p['threshold'],9)}，Recall/Precision/F1/FPR={f(p['recall'])}/{f(p['precision'])}/{f(p['f1'])}/{f(p['fpr'])}，AUROC/AUPRC={f(row['auroc'])}/{f(row['auprc'])}。

| FPR cap | 阈值 | Recall | Precision | F1 | 实际 FPR | TP/FP/TN/FN |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
{chr(10).join(points)}

**实验结论。** {exp_conclusion(row)}
"""


def main():
    leaderboard = json.loads((OUT / "leaderboard.json").read_text(encoding="utf-8"))
    report = json.loads((OUT / "final_report.json").read_text(encoding="utf-8"))
    config = json.loads((OUT / "inference_config.json").read_text(encoding="utf-8"))
    test = json.loads((OUT / "test_scratch" / "test_report.json").read_text(encoding="utf-8"))
    errors = json.loads((OUT / "test_scratch" / "error_analysis.json").read_text(encoding="utf-8"))
    preflight = json.loads((DATA / "preflight_report.json").read_text(encoding="utf-8"))
    runtime = json.loads((OUT / "runtime.json").read_text(encoding="utf-8"))
    stats = manifest_stats()

    overview = []
    for i, row in enumerate(leaderboard, 1):
        p = row["operating_points"]["0.2"]
        model = row.get("family") or row.get("architecture")
        size = row.get("size") or 960
        overview.append(f"| E{i:02d} | {row['name']} | {row['stage']} | {model} | {size} | {row.get('defect_weight','—')} | {f(p['recall'])} | {f(p['fpr'])} | {f(row['auprc'])} |")
    exp_sections = "\n".join(experiment_section(i, row) for i, row in enumerate(leaderboard, 1))

    val = report["validation"]["overall"]
    tm = test["metrics"]
    c1, c2 = config["classifiers"]
    det = config["detector"]

    md = f"""---
title: 齿轮划痕识别 V5 实验详细技术报告
subtitle: 全实验参数 结果 权重来源 分类器与 YOLO 融合设计
date: 2026 年 9 月 29 日
lang: zh-CN
---

**文档性质：** V5 全流程复盘、逐次实验归档、参数与权重溯源、独立测试审计  
**主要入口：** `prepare_scratch_v5.py`、`train_scratch_v5.py`、`infer_scratch_v5.py`、`evaluate_scratch_v5_test.py`  
**证据范围：** `dataset_defects/scratch_v5`、`runs/scratch_v5`、`outputs/scratch_v5`、`docs/Scratch_V5_迁移与集成说明.md`  
**审计日期：** 2026 年 9 月 29 日

## 目录

1. 核心结论
2. 任务定义 数据与验收目标
3. 最终系统结构
4. 实验流程与选择规则
5. 完整公共参数
6. 每次正式实验的参数 内容与结果
7. 分类器和 YOLO 权重的设计与来源
8. 最终验证与锁定测试结果
9. 参数和权重来源总表
10. 方法 算法与公式
11. 误差 泄漏风险与证据边界
12. 复现 推理与文件索引
13. 附录 A 烟雾测试
14. 附录 B 训练过程与审计说明

## 1 核心结论

V5 是只判断“是否存在划痕”的二分类/检测融合系统。正式选择链包含 6 个分类器先导实验、2 个检测器先导实验和 2 个分类器完整复训，共 10 个排行榜实验；运行目录另有 2 个只验证训练链路的烟雾测试。最终系统由 EfficientNet-B0、ResNet18 和 YOLO26-P2 检测器组成。

最终分类器先取等权平均，再和检测器加权：

`p_cls=(p_EfficientNet+p_ResNet)/2`

`p_fused=0.25×p_cls+0.75×p_YOLO=0.125×p_EfficientNet+0.125×p_ResNet+0.75×p_YOLO`

因此，从最终分数的实际贡献系数看，两个分类器各 0.125，YOLO 检测器 0.75。这个比例不是训练损失权重，而是验证集上对 20 个融合候选执行字典序选择得到的推理融合系数。默认阈值为 `{config['default_threshold']:.15f}`。

验证集 150 张上，Recall={f(val['recall'])}、FPR={f(val['fpr'])}，达到预设 Recall≥0.95 且 FPR≤0.20。锁定的独立测试集 150 张上，Recall={f(tm['recall'])}、FPR={f(tm['fpr'])}；FPR 达标，但 Recall 未达标。V5 可作为可运行基线和辅助复核模型，现有证据不足以支持无人值守自动放行。

| 指标 | 验证集 | 锁定测试集 | 目标 | 测试结论 |
| --- | ---: | ---: | ---: | --- |
| 划痕 Recall | {f(val['recall'])} | {f(tm['recall'])} | ≥0.950 | 未达标 |
| Precision | {f(val['precision'])} | {f(tm['precision'])} | 未设硬约束 | 参考 |
| F1 | {f(val['f1'])} | {f(tm['f1'])} | 未设硬约束 | 参考 |
| 正常 FPR | {f(val['fpr'])} | {f(tm['fpr'])} | ≤0.200 | 达标 |
| AUROC | {f(val['auroc'])} | {f(tm['auroc'])} | 未设硬约束 | 参考 |
| AUPRC | {f(val['auprc'])} | {f(tm['auprc'])} | 未设硬约束 | 参考 |
| TP/FP/TN/FN | {val['tp']}/{val['fp']}/{val['tn']}/{val['fn']} | {tm['tp']}/{tm['fp']}/{tm['tn']}/{tm['fn']} | — | — |

## 2 任务定义 数据与验收目标

标签 `y=1` 表示图片有 scratch XML，`y=0` 表示无 XML 且经数据约定视为 normal。模型输出划痕概率；`p_fused≥threshold` 输出 `REJECT`，否则输出 `PASS`。检测框只用于辅助复核，整图决策由融合分数决定。

训练和验证共 514 张图、373 个划痕框。数据准备严格校验 XML 类别、框边界、图像尺寸和标签归一化。train/val 间 SHA256 或 dHash 距离≤2 的 train 侧样本应被排除；本次找到 0 对，因此没有排除样本。

| split | scratch | normal | 总计 | 划痕框 | face | oblique | side |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | {stats['train']['labels']['scratch']} | {stats['train']['labels']['normal']} | {stats['train']['total']} | {stats['train']['boxes']} | {stats['train']['views']['face']} | {stats['train']['views']['oblique']} | {stats['train']['views']['side']} |
| val | {stats['val']['labels']['scratch']} | {stats['val']['labels']['normal']} | {stats['val']['total']} | {stats['val']['boxes']} | {stats['val']['views']['face']} | {stats['val']['views']['oblique']} | {stats['val']['views']['side']} |
| 合计 | 162 | 352 | 514 | 373 | 246 | 245 | 23 |

视角由长短边比 `r=max(width/height,height/width)` 推断：r≥1.8 为 side，1.25≤r<1.8 为 oblique，其余为 face。该视角用于自定义分类器的均衡采样和分组统计，不作为显式输入标签。

主选择目标为 FPR≤0.20 时尽量提高 Recall。每个实验还保存 FPR cap=0.10、0.20、0.30、0.50 四档运行点。锁定测试集包含 31 张划痕、119 张正常、72 个划痕框；它在模型、温度、融合和阈值固定后评估一次。

## 3 最终系统结构

| 分支 | 来源实验 | 输入 | TTA | 温度 | 分支内权重 | 最终总权重 |
| --- | --- | ---: | --- | ---: | ---: | ---: |
| 分类器 1 | `{c1['name']}` | {c1['imgsz']} | {c1['tta']} | {c1['temperature']} | 0.5 | 0.125 |
| 分类器 2 | `{c2['name']}` | {c2['imgsz']} | {c2['tta']} | {c2['temperature']} | 0.5 | 0.125 |
| YOLO 检测器 | `{det['name']}` | {det['imgsz']} | 无 | {det['temperature']} | 1.0 | 0.750 |

分类器按保持宽高比缩放到 384 长边，居中填充到 384×384，填充值 RGB=(238,238,238)，再用 ImageNet mean/std 标准化。检测器由 Ultralytics letterbox 到 960，预测置信度下限 0.001，NMS IoU=0.7；图像级检测分数取所有框置信度最大值。最终配置不启用 TTA。

![V5 验证集混淆矩阵](../outputs/scratch_v5/confusion_matrix.png){{width=63%}}

## 4 实验流程与选择规则

1. 准备 514 张 train/val 数据，转出分类目录和 YOLO 框标签，执行 SHA256/dHash 跨集合检查。
2. 训练 6 个分类候选，比较 ResNet18、EfficientNet-B0、YOLO26n-cls，384/512 输入和正类权重 w1/w2。
3. 训练标准 YOLO26n 和带 P2 高分辨率特征层的 YOLO26-P2 两个 960 检测候选。
4. 每个分类器分别比较 `none` 与四路 `tta_mean`；所有模型用验证集温度缩放。
5. 在 FPR≤0.20 约束下，以 `(满足约束, Recall, −FPR, AUPRC)` 排序候选。
6. 取排名靠前且形状不同的两个分类器设置，执行 100 epoch 上限完整复训；困难样本按 FN=3、FP=2 进行重采样。
7. 最终保留排名前两位分类器与最佳检测器。分类器候选包括两个单模型、mean、max，共 4 个。
8. 对每个分类器候选再测试：单独使用、与检测器按 α=0.25/0.50/0.75 加权、与检测器取 max，共 5 类；总计 4+4×4=20 个融合候选。
9. 仍按 `(满足 FPR≤0.20, Recall, −FPR, AUPRC)` 选出 `weighted_classifier_mean_a0.25`，再由该融合概率扫描默认阈值。
10. 固定全部配置后运行独立测试；测试标签没有进入模型或阈值选择。

## 5 完整公共参数

### 5.1 自定义 ResNet18 / EfficientNet-B0

| 参数组 | 完整有效值 |
| --- | --- |
| 初始化 | torchvision ImageNet 默认预训练；最后分类层替换为 1 个 logit |
| 输入 | 保持比例缩放；灰色 238 正方形填充；384 或 512；RGB |
| 归一化 | mean=(0.485,0.456,0.406)，std=(0.229,0.224,0.225) |
| 损失 | Focal BCE；gamma=1.5；正样本系数为实验 defect_weight=1 或 2 |
| 优化器 | AdamW；lr=3e−4；weight_decay=5e−4 |
| 调度器 | CosineAnnealingLR；T_max=实验 epoch 上限；eta_min=1e−6 |
| batch | 384→24，512→12 |
| 采样器 | WeightedRandomSampler；replacement=true；抽样数=364；基础权重 `1/n_(label,view)` |
| 困难样本 | 最佳先导在 train 上的 FN×3、FP×2；权重与分层采样权重相乘 |
| 数据加载 | 正式训练日志 workers=8；pin_memory=true；persistent_workers=true |
| 精度 | CUDA autocast float16，GradScaler |
| 早停 | 30/35 epoch 级别 patience=10；100 epoch 级别 patience=18 |
| 最佳 checkpoint | 每轮在 FPR cap=0.20 扫阈值；先 Recall，再较低 FPR，再 Precision |
| seed | 20260911；cuDNN/训练未声明 deterministic=true |

随机增强按顺序执行：75% 概率在水平翻转、垂直翻转、90°、270°中选一个；70% 概率亮度 0.82–1.18 且对比度 0.80–1.22；25% CLAHE（clipLimit=2.0，8×8）；15% GaussianBlur 半径 0.1–1.0；20% 高斯噪声 σ=1–5；20% Gamma 0.82–1.18；15% JPEG 压缩 quality=65–92。验证集不做随机增强。

### 5.2 YOLO26n-cls 分类器

| 参数组 | 完整有效值 |
| --- | --- |
| task/model | classify；`yolo26n-cls.pt`；pretrained=true；cls_remap=true |
| 输入/batch | imgsz 384→batch32；imgsz 512→batch16 |
| 优化 | AdamW；lr0=7e−4；lrf=0.01；momentum=0.937；weight_decay=5e−4；nbs=64 |
| warmup | 3 epochs；warmup_momentum=0.8；warmup_bias_lr=0.1 |
| 设备 | CUDA 0；AMP=true；cache=ram；workers=8；deterministic=false |
| 早停 | patience=10；epoch 上限=30 |
| 几何增强 | scale/degrees/translate/shear/perspective=0；fliplr=0.5；flipud=0.5 |
| 颜色增强 | hsv_h=0.003；hsv_s=0.10；hsv_v=0.15；bgr=0 |
| 关闭项 | erasing=0；auto_augment=null；mixup/cutmix/copy_paste=0；dropout=0 |
| 验证/保存 | val=true；split=val；save=true；plots=true；exist_ok=true |

YOLO 分类实验的 `defect_weight` 不是 Ultralytics 损失项。w2 通过把每张 train/scratch 图复制为两份改变训练频率；w1 保留一份。val 不复制。

### 5.3 YOLO26 检测器

| 参数组 | 完整有效值 |
| --- | --- |
| task/model | detect；标准头=`yolo26n.pt`；P2=`yolo26-p2.yaml` 加载 `yolo26n.pt` |
| 输入/batch | imgsz=960；标准 batch=12；P2 batch=6；OOM 时逐次减半 |
| 优化 | AdamW；lr0=8e−4；lrf=0.01；momentum=0.937；weight_decay=5e−4；nbs=64 |
| warmup | 3 epochs；warmup_momentum=0.8；warmup_bias_lr=0.1 |
| 设备 | CUDA 0；AMP=true；cache=ram；workers≤4；deterministic=false |
| 训练长度 | epoch=35；patience=12 |
| 损失超参记录 | box=7.5；cls=0.5；dfl=1.5；Ultralytics 结果实际记录 box/cls/l1 loss |
| 几何增强 | mosaic/mixup/cutmix=0；degrees=0；translate=0.01；scale=0.05；fliplr=flipud=0.5 |
| 颜色增强 | hsv_h=0.003；hsv_s=0.10；hsv_v=0.12 |
| 推理 | conf_floor=0.001；NMS IoU=0.7；max_det=300；图像级分数=max box confidence |
| 验证/保存 | val=true；split=val；plots=true；save=true |

这里的 box=7.5、cls=0.5、dfl=1.5 是 Ultralytics 配置中的检测损失权重，V5 没有对它们做独立搜索；它们属于框架先验。V5 实际搜索的是标准/P2 架构、图像级温度、融合 α 和最终阈值。

### 5.4 共同校准与阈值

温度 T 在 [0.35,4.00] 的 147 个等距点上扫描，步长 0.025，以验证集二元 NLL 最小为准。阈值候选为 {{0,1}} 与全部验证概率，按 `(FPR≤cap, Recall, −FPR, Precision)` 取最大。分类器 TTA 候选为原图和 `原图+水平翻转+垂直翻转+CLAHE` 四路均值。

### 5.5 正式实验总览

正式训练环境记录为 Python 3.13.12、PyTorch 2.14.0+cu130、torchvision 0.29.0+cu130、Ultralytics 8.4.142、NumPy 2.5.2、Pillow 12.3.0、OpenCV 5.0.0，GPU 为 NVIDIA GeForce RTX 4060 Laptop GPU 8GB。最后一次 `finalize-only` 把 `runtime.json` 的 workers 更新为 4；实际主训练与恢复日志开头均记录 workers=8，YOLO 检测器内部再限制为 4。

| ID | 实验 | 阶段 | 模型/结构 | 输入 | w | Recall | FPR | AUPRC |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(overview)}

## 6 每次正式实验的参数 内容与结果

每个实验的完整有效参数由第 5 章对应模型族公共参数与本节差异参数共同构成；各 YOLO 运行目录的 `args.yaml` 保存包括非训练开关在内的原始全字段。以下结果均是温度校准后验证集结果，主比较档为 FPR cap=0.20。

{exp_sections}

## 7 分类器和 YOLO 权重的设计与来源

### 7.1 自定义分类器损失权重

自定义分类器使用 Focal BCE：

`L=mean[w(y)×(1−p_t)^γ×BCEWithLogits(z,y)]`

其中 `p=σ(z)`，`p_t=y·p+(1−y)·(1−p)`，γ=1.5，`w(y)=w_pos` 当 y=1，否则为 1。w_pos 比较 1 和 2。ResNet 的 384/w1 在 FPR≤0.20 时 Recall/FPR=0.930/0.140，512/w2 为 0.930/0.196；EfficientNet 的 384/w1 为 0.930/0.168，512/w2 为 0.860/0.178。w2 没有稳定收益，因此最终两个分类器都采用 w1。

### 7.2 分层采样与困难样本权重

训练样本基础抽样权重为 `s_i=1/n_(label,view)`，使 normal/scratch × face/oblique/side 六个存在的分层在期望上更均衡。困难样本乘数为：训练集漏检 scratch 取 3，训练集误报 normal 取 2，其余取 1，故最终抽样权重为 `s'_i=s_i×h_i`。本轮 `classifier_hard_cases.json` 只记录 `train_384:2.0`，说明最终完整复训实际只有这一张训练误报被额外加权；没有生成 detector_hard_cases，检测器没有完成困难样本长训。

### 7.3 YOLO 分类权重

YOLO26n-cls 的 w1/w2 通过复制正类文件实现，近似改变经验分布：`N_scratch'=w×N_scratch`，不是把 YOLO 分类损失乘以 w。w2 的两项实验都弱于对应 384/w1 候选，因此 YOLO 分类模型没有进入最终融合。

### 7.4 YOLO 检测损失权重

检测运行的原始 `args.yaml` 记录 box=7.5、cls=0.5、dfl=1.5。这些值来自本轮使用的 Ultralytics 默认/框架配置，两个检测实验保持一致，并未通过 V5 消融得到。P2 相对标准头只改变特征层结构和 batch，目的是保留更高分辨率特征以感知小划痕。

### 7.5 推理融合权重

最终先对两个分类器做等权均值，再扫描 α∈{{0.25,0.50,0.75}}：

`p(α)=α×p_cls+(1−α)×p_det`

同时比较 max 软 OR。20 个候选中 α=0.25 的分类器均值方案按主排序胜出，得到验证 Recall=0.977、FPR=0.084、AUPRC=0.937。α=0.25 表示分类器整体占 25%，检测器占 75%；由于分类器内部等权，各分类器占最终分数 12.5%。这些数值只在当前验证集上成立，不等同于可解释的因果贡献度。

### 7.6 温度权重与阈值

最终温度分别为 EfficientNet 0.7、ResNet 2.05、P2 检测器 2.125。T<1 会把概率推离 0.5，T>1 会压缩向 0.5。温度是验证 NLL 的校准参数，不是模型投票权重。默认阈值 0.300273610279458 来自最终融合在 FPR cap=0.20 下的离散扫描。

## 8 最终验证与锁定测试结果

### 8.1 验证集

最终融合在验证集 TP/FP/TN/FN={val['tp']}/{val['fp']}/{val['tn']}/{val['fn']}。划痕分视角 Recall：face={f(report['validation']['views']['face']['recall'])}（n={report['validation']['views']['face']['count']}），oblique={f(report['validation']['views']['oblique']['recall'])}（n={report['validation']['views']['oblique']['count']}），side={f(report['validation']['views']['side']['recall'])}（n={report['validation']['views']['side']['count']}）。side 只有 1 张，不能据此估计稳定泛化性能。

验证集的高敏感阈值 0.203814 能达到 Recall=1.0，但验证 FPR=0.402。它不是默认阈值。

### 8.2 锁定独立测试

固定阈值下测试 TP/FP/TN/FN={tm['tp']}/{tm['fp']}/{tm['tn']}/{tm['fn']}。31 张划痕漏掉 6 张；119 张正常误报 20 张。测试 Recall 的 Wilson 95% 区间约为 0.637–0.908，样本仍较少。预存的高敏感阈值 0.203814 在测试 Recall=0.935，但 FPR=0.588，不能替换默认阈值。

![V5 独立测试漏检样例](../outputs/scratch_v5/test_scratch/false_negatives.jpg){{width=92%}}

![V5 独立测试误报样例](../outputs/scratch_v5/test_scratch/false_positives.jpg){{width=92%}}

### 8.3 错误分支均值

| 类型 | n | 分类器均值 | 检测器均值 | 亮度 | 对比度 |
| --- | ---: | ---: | ---: | ---: | ---: |
| TP | {errors['true_positive']['count']} | {f(errors['true_positive']['mean_classifier_probability'])} | {f(errors['true_positive']['mean_detector_probability'])} | {f(errors['true_positive']['mean_brightness'])} | {f(errors['true_positive']['mean_contrast'])} |
| FN | {errors['false_negative']['count']} | {f(errors['false_negative']['mean_classifier_probability'])} | {f(errors['false_negative']['mean_detector_probability'])} | {f(errors['false_negative']['mean_brightness'])} | {f(errors['false_negative']['mean_contrast'])} |
| TN | {errors['true_negative']['count']} | {f(errors['true_negative']['mean_classifier_probability'])} | {f(errors['true_negative']['mean_detector_probability'])} | {f(errors['true_negative']['mean_brightness'])} | {f(errors['true_negative']['mean_contrast'])} |
| FP | {errors['false_positive']['count']} | {f(errors['false_positive']['mean_classifier_probability'])} | {f(errors['false_positive']['mean_detector_probability'])} | {f(errors['false_positive']['mean_brightness'])} | {f(errors['false_positive']['mean_contrast'])} |

FN 的分类器与检测器均值都低，说明只调整 α 很难根治；FP 的分类器均值高达 0.814，符合侧齿高光和正常加工纹被分类器当成划痕纹理的错误模式。

## 9 参数和权重来源总表

| 参数/权重 | 最终值 | 来源实验或规则 | 证据性质 |
| --- | --- | --- | --- |
| 任务标签 | normal/scratch | XML 是否存在及数据约定 | 任务定义 |
| 数据拆分 | train 364 / val 150 | 现有来源目录；dHash/SHA256 检查 | 数据设计 |
| 模型族 | EfficientNet+ResNet+YOLO-P2 | 6 分类+2 检测候选 | 验证实验 |
| 分类输入 | 384 | 384/w1 对 512/w2 候选 | 验证实验，输入与 w 同时变化，不能完全解耦 |
| 自定义正类损失权重 | 1 | w1/w2 组合对比 | 验证实验 |
| YOLO-cls 正类复制权重 | 未采用；候选 w1/w2 | 两个 YOLO 分类实验 | 被否决方案 |
| Focal gamma | 1.5 | 训练脚本固定 | 工程先验，未消融 |
| 分层采样 | `1/n_(label,view)` | 训练脚本固定 | 工程设计 |
| hard-case 乘数 | FN 3，FP 2 | 训练脚本固定；本轮实际 1 个 FP×2 | 工程设计 |
| 检测结构 | YOLO26-P2 | 标准头与 P2 对比 | 验证实验 |
| YOLO box/cls/dfl | 7.5/0.5/1.5 | Ultralytics args | 框架先验，未消融 |
| 分类器内部权重 | 0.5/0.5 | mean 与单模型/max 对比 | 融合搜索 |
| 分类/检测权重 | 0.25/0.75 | α=0.25/0.50/0.75 与 max 搜索 | 融合搜索 |
| 三模型最终总权重 | 0.125/0.125/0.75 | 两层公式展开 | 由融合规则推导 |
| TTA | none | 每分类器 none 与 tta_mean 对比 | 验证实验 |
| 温度 | 0.7/2.05/2.125 | 147 点 NLL 网格 | 验证校准 |
| 默认阈值 | 0.300273610279458 | 融合概率 FPR cap=0.20 扫描 | 验证实验 |
| AdamW/lr/增强 | 见第 5 章 | 脚本固定 | 工程先验，未独立消融 |

## 10 方法 算法与公式

### 10.1 指标

`Recall=TP/(TP+FN)`；`Precision=TP/(TP+FP)`；`FPR=FP/(FP+TN)`；`Specificity=1−FPR`；`F1=2PR/(P+R)`；`NPV=TN/(TN+FN)`。

### 10.2 余弦退火

`lr_t=η_min+0.5(lr_0−η_min)[1+cos(πt/T_max)]`，其中 lr0=3e−4，η_min=1e−6。早停可能在完整周期结束前结束训练。

### 10.3 温度缩放

先取 `l=log[p/(1−p)]`，再计算 `p_T=σ(l/T)`。目标函数：`NLL(T)=−(1/N)Σ[y log p_T+(1−y)log(1−p_T)]`。温度缩放不改变同一模型样本的排序，但会改变概率数值以及跨模型融合关系。

### 10.4 TTA

`p_TTA=(p_original+p_hflip+p_vflip+p_CLAHE)/4`。V5 对每个分类器比较它与无 TTA，最终三个成员均使用无 TTA。

### 10.5 IoU 与框匹配

`IoU(A,B)=|A∩B|/|A∪B|`。预测框按置信度阈值过滤后，对每个预测框贪心匹配尚未匹配的最高 IoU 真值框；IoU 达到 0.3 或 0.5 计 TP，否则计 FP，未匹配真值计 FN。

### 10.6 AUROC/AUPRC

样本按概率降序排列；AUROC 用 ROC 折线梯形积分，AUPRC 用 Recall 增量乘当前 Precision 的阶梯积分。验证集只有 43 个正类和 107 个负类，Recall/FPR 的最小离散步长分别约 0.0233/0.00935。

## 11 误差 泄漏风险与证据边界

train/val 预检没有发现 dHash≤2 或 SHA256 跨集合对。独立测试相对于 train+val 没有 SHA256 完全重复，但发现 75 个 dHash≤2 的跨集合相似对，部分 dHash 距离为 0。固定背景和相似齿轮轮廓会使 dHash 产生大量相似提示，因此这不等价于确认数据泄漏；同时它确实意味着独立性证据不能只靠 dHash，需要人工复核或使用基于局部纹理/特征向量的重复检测。

验证指标同时用于模型、TTA、温度、融合和阈值选择，存在验证集过拟合风险。最终测试在选择后锁定执行，可信度高于验证集，但 31 个正类仍不足以精确证明 95% Recall。测试失败说明验证 Recall 高估了泛化能力。

P2 检测器的图像级 AUPRC 较好，但框级精度极低：IoU=0.3 时 FP=927。其 0.75 融合权重只代表“最高框分数对整图分类有用”，不能解释为检测框定位已经可靠。框只适合辅助显示。

`final_report.json` 的 elapsed_hours=0.0178 记录的是最后一次复用现有权重并重建输出的流程，不是完整训练总耗时。训练日志还记录约 0.328h 和 0.230h 的运行，且包含失败后恢复/重复处理，不能简单相加为准确总训练时间。当前 `runtime.json` 的 workers=4 同样来自最后一次重建；正式训练日志与 YOLO 分类 `args.yaml` 记录 workers=8，检测 `args.yaml` 记录 workers=4。

## 12 复现 推理与文件索引

```powershell
& ".venv\\Scripts\\python.exe" "prepare_scratch_v5.py"
& ".venv\\Scripts\\python.exe" "train_scratch_v5.py" --hours 6 --workers 4
& ".venv\\Scripts\\python.exe" "infer_scratch_v5.py" "图片或目录" --config "outputs\\scratch_v5\\inference_config.json"
& ".venv\\Scripts\\python.exe" "evaluate_scratch_v5_test.py"
```

| 证据 | 路径 | 用途 |
| --- | --- | --- |
| 数据准备 | `prepare_scratch_v5.py` | 标签、YOLO 框、泄漏检查 |
| 训练与选择 | `train_scratch_v5.py` | 全候选、损失、采样、校准、融合 |
| 推理 | `infer_scratch_v5.py` | 三模型加载、融合、判定 |
| 锁定测试 | `evaluate_scratch_v5_test.py` | 独立测试与覆盖保护 |
| 数据清单 | `dataset_defects/scratch_v5/scratch_manifest.csv` | 每图标签、尺寸、哈希、排除状态 |
| 预检 | `dataset_defects/scratch_v5/preflight_report.json` | 数量、框数、重复检查 |
| 正式排行榜 | `outputs/scratch_v5/leaderboard.json` | 10 个实验四档运行点 |
| 最终配置 | `outputs/scratch_v5/inference_config.json` | 成员、温度、权重、阈值 |
| 验证结果 | `outputs/scratch_v5/final_report.json` | 胜者与验证指标 |
| 测试结果 | `outputs/scratch_v5/test_scratch/test_report.json` | 锁定测试指标 |
| 逐图测试 | `outputs/scratch_v5/test_scratch/test_predictions.csv` | 150 张图三分支概率和决策 |
| 完整 YOLO 参数 | `runs/scratch_v5/*/args.yaml` | 每个 YOLO 运行的原始全字段 |
| 训练轨迹 | `runs/scratch_v5/*/history.json` / `results.csv` | epoch、loss、mAP/top1 |

## 13 附录 A 烟雾测试

两项 smoke 只检查数据加载、前向/反向、保存和验证链路，不参与正式排行榜或融合选择。

| 运行 | 参数 | 实际结果 | 解释 |
| --- | --- | --- | --- |
| `smoke_resnet18_384` | ResNet18，384，1 epoch，seed=123；验证子集 32 张 | Recall=0.444，Precision=0.500，FPR=0.174，TP/FP/TN/FN=4/4/19/5 | 连通性验证，不能与 150 张正式 val 等价比较 |
| `smoke_detector_standard_960` | YOLO26n 标准头，960，batch12，1 epoch，seed=123，workers=2 | 框 P/R/mAP50/mAP50-95=0.0006/0.2842/0.00033/0.00007 | 检查检测训练可执行，性能无选择意义 |

推理另有两张冒烟样本：`val_001` 历史融合概率约 0.0693，应为 PASS；`val_017` 约 0.7392，应为 REJECT。

## 14 附录 B 训练过程与审计说明

标准检测器的 `results.csv` 有 37 行而配置 epoch 上限为 35，`args.yaml` 记录从 `last.pt` resume；这是中断恢复留下的重复/追加记录，不应解释为独立的 37-epoch 新实验。训练日志中两个检测实验一度在训练后报 `OSError(22, Invalid argument)`，随后已有完整权重和结果被重新载入并进入最终排行榜。

本报告采用以下证据优先级：最终 `inference_config.json` 与锁定 `test_report.json` 决定部署配置和测试结论；`leaderboard.json` 决定正式实验结果；`args.yaml`、`history.json`、`results.csv` 决定真实训练参数和轨迹；总结性 Markdown 只用于交叉核对。原 Windows 路径是历史运行环境痕迹，最终推理配置使用相对路径，能够随模型包迁移。

正式实验的“完整参数”采用公共参数加差异参数表达；这与每个运行的原始参数一一对应，同时避免把 `show`、`save_crop`、导出格式等未参与训练的 CLI 默认项重复十次。需要逐字段审计时，以相应 `args.yaml` 为最终依据。
"""
    REPORT.write_text(md, encoding="utf-8")


if __name__ == "__main__":
    main()
