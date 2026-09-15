# p_det_one_class_include_difficult_standard_960

- 状态：`完成`
- 类型：`detector`
- 阶段：`pilot`
- difficult 策略：`include_difficult`
- 输入尺寸：`960`
- 计划轮数：`35`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\p_det_one_class_include_difficult_standard_960\weights\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.9706 | 0.7333 | 0.8354 | 0.1846 | 33/12/53/1 | 0.9778 | 0.9658 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "p_det_one_class_include_difficult_standard_960",
  "kind": "detector",
  "scheme": "one_class",
  "difficult_policy": "include_difficult",
  "architecture": "standard",
  "imgsz": 960,
  "epochs": 35,
  "stage": "pilot",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\p_det_one_class_include_difficult_standard_960\\weights\\best.pt",
  "tta": "none",
  "temperature": 2.0,
  "operating_points": {
    "0.1": {
      "threshold": 0.16337386732277615,
      "recall": 0.9117647058823529,
      "precision": 0.9117647058823529,
      "f1": 0.9117647058823528,
      "fpr": 0.046153846153846156,
      "specificity": 0.9538461538461538,
      "tp": 31,
      "fp": 3,
      "tn": 62,
      "fn": 3
    },
    "0.2": {
      "threshold": 0.10583301166137314,
      "recall": 0.9705882352941176,
      "precision": 0.7333333333333333,
      "f1": 0.8354430379746834,
      "fpr": 0.18461538461538463,
      "specificity": 0.8153846153846154,
      "tp": 33,
      "fp": 12,
      "tn": 53,
      "fn": 1
    },
    "0.3": {
      "threshold": 0.07455426412666971,
      "recall": 1.0,
      "precision": 0.6538461538461539,
      "f1": 0.7906976744186047,
      "fpr": 0.27692307692307694,
      "specificity": 0.7230769230769231,
      "tp": 34,
      "fp": 18,
      "tn": 47,
      "fn": 0
    },
    "0.5": {
      "threshold": 0.07455426412666971,
      "recall": 1.0,
      "precision": 0.6538461538461539,
      "f1": 0.7906976744186047,
      "fpr": 0.27692307692307694,
      "specificity": 0.7230769230769231,
      "tp": 34,
      "fp": 18,
      "tn": 47,
      "fn": 0
    }
  },
  "primary": {
    "threshold": 0.10583301166137314,
    "recall": 0.9705882352941176,
    "precision": 0.7333333333333333,
    "f1": 0.8354430379746834,
    "fpr": 0.18461538461538463,
    "specificity": 0.8153846153846154,
    "tp": 33,
    "fp": 12,
    "tn": 53,
    "fn": 1
  },
  "auroc": 0.9778280542986425,
  "auprc": 0.9657730850514259,
  "groups": {
    "bottom": {
      "images": 11,
      "recall": 0.9090909090909091
    },
    "oblique": {
      "images": 12,
      "recall": 1.0
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
