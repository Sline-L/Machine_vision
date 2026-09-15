# p_det_two_class_include_difficult_p2_960

- 状态：`完成`
- 类型：`detector`
- 阶段：`pilot`
- difficult 策略：`include_difficult`
- 输入尺寸：`960`
- 计划轮数：`35`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\p_det_two_class_include_difficult_p2_960\weights\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.9412 | 0.8205 | 0.8767 | 0.1077 | 32/7/58/2 | 0.9520 | 0.9220 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "p_det_two_class_include_difficult_p2_960",
  "kind": "detector",
  "scheme": "two_class",
  "difficult_policy": "include_difficult",
  "architecture": "p2",
  "imgsz": 960,
  "epochs": 35,
  "stage": "pilot",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\p_det_two_class_include_difficult_p2_960\\weights\\best.pt",
  "tta": "none",
  "temperature": 3.05,
  "operating_points": {
    "0.1": {
      "threshold": 0.23010438149465742,
      "recall": 0.9117647058823529,
      "precision": 0.8857142857142857,
      "f1": 0.8985507246376812,
      "fpr": 0.06153846153846154,
      "specificity": 0.9384615384615385,
      "tp": 31,
      "fp": 4,
      "tn": 61,
      "fn": 3
    },
    "0.2": {
      "threshold": 0.2063931899999477,
      "recall": 0.9411764705882353,
      "precision": 0.8205128205128205,
      "f1": 0.8767123287671232,
      "fpr": 0.1076923076923077,
      "specificity": 0.8923076923076922,
      "tp": 32,
      "fp": 7,
      "tn": 58,
      "fn": 2
    },
    "0.3": {
      "threshold": 0.2063931899999477,
      "recall": 0.9411764705882353,
      "precision": 0.8205128205128205,
      "f1": 0.8767123287671232,
      "fpr": 0.1076923076923077,
      "specificity": 0.8923076923076922,
      "tp": 32,
      "fp": 7,
      "tn": 58,
      "fn": 2
    },
    "0.5": {
      "threshold": 0.11899848309587273,
      "recall": 1.0,
      "precision": 0.53125,
      "f1": 0.6938775510204082,
      "fpr": 0.46153846153846156,
      "specificity": 0.5384615384615384,
      "tp": 34,
      "fp": 30,
      "tn": 35,
      "fn": 0
    }
  },
  "primary": {
    "threshold": 0.2063931899999477,
    "recall": 0.9411764705882353,
    "precision": 0.8205128205128205,
    "f1": 0.8767123287671232,
    "fpr": 0.1076923076923077,
    "specificity": 0.8923076923076922,
    "tp": 32,
    "fp": 7,
    "tn": 58,
    "fn": 2
  },
  "auroc": 0.9520361990950226,
  "auprc": 0.9220239133929391,
  "groups": {
    "bottom": {
      "images": 11,
      "recall": 0.9090909090909091
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
