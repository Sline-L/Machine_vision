# f_det_one_class_exclude_difficult_standard_1280

- 状态：`完成`
- 类型：`detector`
- 阶段：`full`
- difficult 策略：`exclude_difficult`
- 输入尺寸：`1280`
- 计划轮数：`100`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\f_det_one_class_exclude_difficult_standard_1280\weights\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.8824 | 0.7500 | 0.8108 | 0.1538 | 30/10/55/4 | 0.9299 | 0.9128 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "f_det_one_class_exclude_difficult_standard_1280",
  "kind": "detector",
  "scheme": "one_class",
  "difficult_policy": "exclude_difficult",
  "architecture": "standard",
  "imgsz": 1280,
  "epochs": 100,
  "stage": "full",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\f_det_one_class_exclude_difficult_standard_1280\\weights\\best.pt",
  "tta": "none",
  "temperature": 3.625,
  "operating_points": {
    "0.1": {
      "threshold": 0.3521110316741965,
      "recall": 0.7647058823529411,
      "precision": 0.896551724137931,
      "f1": 0.8253968253968255,
      "fpr": 0.046153846153846156,
      "specificity": 0.9538461538461538,
      "tp": 26,
      "fp": 3,
      "tn": 62,
      "fn": 8
    },
    "0.2": {
      "threshold": 0.2391816052014593,
      "recall": 0.8823529411764706,
      "precision": 0.75,
      "f1": 0.8108108108108107,
      "fpr": 0.15384615384615385,
      "specificity": 0.8461538461538461,
      "tp": 30,
      "fp": 10,
      "tn": 55,
      "fn": 4
    },
    "0.3": {
      "threshold": 0.20512174010994458,
      "recall": 0.9117647058823529,
      "precision": 0.6595744680851063,
      "f1": 0.7654320987654322,
      "fpr": 0.24615384615384617,
      "specificity": 0.7538461538461538,
      "tp": 31,
      "fp": 16,
      "tn": 49,
      "fn": 3
    },
    "0.5": {
      "threshold": 0.17252445193392388,
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
    "threshold": 0.2391816052014593,
    "recall": 0.8823529411764706,
    "precision": 0.75,
    "f1": 0.8108108108108107,
    "fpr": 0.15384615384615385,
    "specificity": 0.8461538461538461,
    "tp": 30,
    "fp": 10,
    "tn": 55,
    "fn": 4
  },
  "auroc": 0.9298642533936652,
  "auprc": 0.9128344540279424,
  "groups": {
    "bottom": {
      "images": 11,
      "recall": 0.8181818181818182
    },
    "oblique": {
      "images": 12,
      "recall": 0.9166666666666666
    },
    "side": {
      "images": 14,
      "recall": 0.9285714285714286
    },
    "difficult": {
      "images": 3,
      "recall": 0.3333333333333333
    }
  }
}
```
