# p_det_two_class_include_difficult_standard_960

- 状态：`完成`
- 类型：`detector`
- 阶段：`pilot`
- difficult 策略：`include_difficult`
- 输入尺寸：`960`
- 计划轮数：`35`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\p_det_two_class_include_difficult_standard_960\weights\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.9118 | 0.8158 | 0.8611 | 0.1077 | 31/7/58/3 | 0.9466 | 0.9091 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "p_det_two_class_include_difficult_standard_960",
  "kind": "detector",
  "scheme": "two_class",
  "difficult_policy": "include_difficult",
  "architecture": "standard",
  "imgsz": 960,
  "epochs": 35,
  "stage": "pilot",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\p_det_two_class_include_difficult_standard_960\\weights\\best.pt",
  "tta": "none",
  "temperature": 1.8249999999999997,
  "operating_points": {
    "0.1": {
      "threshold": 0.1631826503997718,
      "recall": 0.8823529411764706,
      "precision": 0.8823529411764706,
      "f1": 0.8823529411764706,
      "fpr": 0.06153846153846154,
      "specificity": 0.9384615384615385,
      "tp": 30,
      "fp": 4,
      "tn": 61,
      "fn": 4
    },
    "0.2": {
      "threshold": 0.1312930821803135,
      "recall": 0.9117647058823529,
      "precision": 0.8157894736842105,
      "f1": 0.861111111111111,
      "fpr": 0.1076923076923077,
      "specificity": 0.8923076923076922,
      "tp": 31,
      "fp": 7,
      "tn": 58,
      "fn": 3
    },
    "0.3": {
      "threshold": 0.1312930821803135,
      "recall": 0.9117647058823529,
      "precision": 0.8157894736842105,
      "f1": 0.861111111111111,
      "fpr": 0.1076923076923077,
      "specificity": 0.8923076923076922,
      "tp": 31,
      "fp": 7,
      "tn": 58,
      "fn": 3
    },
    "0.5": {
      "threshold": 0.05463465651051924,
      "recall": 0.9705882352941176,
      "precision": 0.5892857142857143,
      "f1": 0.7333333333333333,
      "fpr": 0.35384615384615387,
      "specificity": 0.6461538461538461,
      "tp": 33,
      "fp": 23,
      "tn": 42,
      "fn": 1
    }
  },
  "primary": {
    "threshold": 0.1312930821803135,
    "recall": 0.9117647058823529,
    "precision": 0.8157894736842105,
    "f1": 0.861111111111111,
    "fpr": 0.1076923076923077,
    "specificity": 0.8923076923076922,
    "tp": 31,
    "fp": 7,
    "tn": 58,
    "fn": 3
  },
  "auroc": 0.9466063348416289,
  "auprc": 0.9091002958643016,
  "groups": {
    "bottom": {
      "images": 11,
      "recall": 0.9090909090909091
    },
    "oblique": {
      "images": 12,
      "recall": 0.8333333333333334
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
