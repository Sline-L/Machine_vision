# p_cls_yolo_cls_384_exclude_difficult

- 状态：`完成`
- 类型：`classifier`
- 阶段：`pilot`
- difficult 策略：`exclude_difficult`
- 输入尺寸：`384`
- 计划轮数：`30`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\p_cls_yolo_cls_384_exclude_difficult\weights\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.8529 | 0.7250 | 0.7838 | 0.1692 | 29/11/54/5 | 0.8810 | 0.7825 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "p_cls_yolo_cls_384_exclude_difficult",
  "kind": "classifier",
  "family": "yolo_cls",
  "imgsz": 384,
  "difficult_policy": "exclude_difficult",
  "epochs": 30,
  "stage": "pilot",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\p_cls_yolo_cls_384_exclude_difficult\\weights\\best.pt",
  "tta": "rot90",
  "temperature": 4.0,
  "operating_points": {
    "0.1": {
      "threshold": 0.7202186798505538,
      "recall": 0.5588235294117647,
      "precision": 0.7916666666666666,
      "f1": 0.6551724137931034,
      "fpr": 0.07692307692307693,
      "specificity": 0.9230769230769231,
      "tp": 19,
      "fp": 5,
      "tn": 60,
      "fn": 15
    },
    "0.2": {
      "threshold": 0.6739555741937255,
      "recall": 0.8529411764705882,
      "precision": 0.725,
      "f1": 0.7837837837837837,
      "fpr": 0.16923076923076924,
      "specificity": 0.8307692307692307,
      "tp": 29,
      "fp": 11,
      "tn": 54,
      "fn": 5
    },
    "0.3": {
      "threshold": 0.6471282094789439,
      "recall": 0.9117647058823529,
      "precision": 0.6326530612244898,
      "f1": 0.746987951807229,
      "fpr": 0.27692307692307694,
      "specificity": 0.7230769230769231,
      "tp": 31,
      "fp": 18,
      "tn": 47,
      "fn": 3
    },
    "0.5": {
      "threshold": 0.6417112448285069,
      "recall": 0.9411764705882353,
      "precision": 0.6153846153846154,
      "f1": 0.744186046511628,
      "fpr": 0.3076923076923077,
      "specificity": 0.6923076923076923,
      "tp": 32,
      "fp": 20,
      "tn": 45,
      "fn": 2
    }
  },
  "primary": {
    "threshold": 0.6739555741937255,
    "recall": 0.8529411764705882,
    "precision": 0.725,
    "f1": 0.7837837837837837,
    "fpr": 0.16923076923076924,
    "specificity": 0.8307692307692307,
    "tp": 29,
    "fp": 11,
    "tn": 54,
    "fn": 5
  },
  "auroc": 0.8809954751131222,
  "auprc": 0.7825084951875618,
  "groups": {
    "bottom": {
      "images": 11,
      "recall": 0.6363636363636364
    },
    "oblique": {
      "images": 12,
      "recall": 0.9166666666666666
    },
    "side": {
      "images": 14,
      "recall": 1.0
    },
    "difficult": {
      "images": 3,
      "recall": 0.6666666666666666
    }
  }
}
```
