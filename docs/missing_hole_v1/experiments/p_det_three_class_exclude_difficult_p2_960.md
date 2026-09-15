# p_det_three_class_exclude_difficult_p2_960

- 状态：`完成`
- 类型：`detector`
- 阶段：`pilot`
- difficult 策略：`exclude_difficult`
- 输入尺寸：`960`
- 计划轮数：`35`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\p_det_three_class_exclude_difficult_p2_960\weights\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.9118 | 0.7561 | 0.8267 | 0.1538 | 31/10/55/3 | 0.9434 | 0.9073 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "p_det_three_class_exclude_difficult_p2_960",
  "kind": "detector",
  "scheme": "three_class",
  "difficult_policy": "exclude_difficult",
  "architecture": "p2",
  "imgsz": 960,
  "epochs": 35,
  "stage": "pilot",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\p_det_three_class_exclude_difficult_p2_960\\weights\\best.pt",
  "tta": "none",
  "temperature": 2.175,
  "operating_points": {
    "0.1": {
      "threshold": 0.22752098773544055,
      "recall": 0.8529411764705882,
      "precision": 0.8529411764705882,
      "f1": 0.8529411764705882,
      "fpr": 0.07692307692307693,
      "specificity": 0.9230769230769231,
      "tp": 29,
      "fp": 5,
      "tn": 60,
      "fn": 5
    },
    "0.2": {
      "threshold": 0.13596742765818423,
      "recall": 0.9117647058823529,
      "precision": 0.7560975609756098,
      "f1": 0.8266666666666665,
      "fpr": 0.15384615384615385,
      "specificity": 0.8461538461538461,
      "tp": 31,
      "fp": 10,
      "tn": 55,
      "fn": 3
    },
    "0.3": {
      "threshold": 0.10014852839431665,
      "recall": 0.9411764705882353,
      "precision": 0.6274509803921569,
      "f1": 0.7529411764705882,
      "fpr": 0.2923076923076923,
      "specificity": 0.7076923076923076,
      "tp": 32,
      "fp": 19,
      "tn": 46,
      "fn": 2
    },
    "0.5": {
      "threshold": 0.0868757762809266,
      "recall": 0.9705882352941176,
      "precision": 0.6226415094339622,
      "f1": 0.7586206896551724,
      "fpr": 0.3076923076923077,
      "specificity": 0.6923076923076923,
      "tp": 33,
      "fp": 20,
      "tn": 45,
      "fn": 1
    }
  },
  "primary": {
    "threshold": 0.13596742765818423,
    "recall": 0.9117647058823529,
    "precision": 0.7560975609756098,
    "f1": 0.8266666666666665,
    "fpr": 0.15384615384615385,
    "specificity": 0.8461538461538461,
    "tp": 31,
    "fp": 10,
    "tn": 55,
    "fn": 3
  },
  "auroc": 0.9434389140271493,
  "auprc": 0.9073067538921774,
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
      "recall": 1.0
    },
    "difficult": {
      "images": 3,
      "recall": 0.0
    }
  }
}
```
