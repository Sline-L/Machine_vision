# p_det_three_class_include_difficult_p2_960

- 状态：`完成`
- 类型：`detector`
- 阶段：`pilot`
- difficult 策略：`include_difficult`
- 输入尺寸：`960`
- 计划轮数：`35`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\p_det_three_class_include_difficult_p2_960\weights\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.9412 | 0.8205 | 0.8767 | 0.1077 | 32/7/58/2 | 0.9588 | 0.9467 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "p_det_three_class_include_difficult_p2_960",
  "kind": "detector",
  "scheme": "three_class",
  "difficult_policy": "include_difficult",
  "architecture": "p2",
  "imgsz": 960,
  "epochs": 35,
  "stage": "pilot",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\p_det_three_class_include_difficult_p2_960\\weights\\best.pt",
  "tta": "none",
  "temperature": 1.4249999999999998,
  "operating_points": {
    "0.1": {
      "threshold": 0.15788676394736753,
      "recall": 0.9117647058823529,
      "precision": 0.8378378378378378,
      "f1": 0.8732394366197184,
      "fpr": 0.09230769230769231,
      "specificity": 0.9076923076923077,
      "tp": 31,
      "fp": 6,
      "tn": 59,
      "fn": 3
    },
    "0.2": {
      "threshold": 0.1240743863029647,
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
      "threshold": 0.1240743863029647,
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
      "threshold": 0.03714650092473373,
      "recall": 0.9705882352941176,
      "precision": 0.5238095238095238,
      "f1": 0.6804123711340205,
      "fpr": 0.46153846153846156,
      "specificity": 0.5384615384615384,
      "tp": 33,
      "fp": 30,
      "tn": 35,
      "fn": 1
    }
  },
  "primary": {
    "threshold": 0.1240743863029647,
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
  "auroc": 0.9588235294117647,
  "auprc": 0.946745116386423,
  "groups": {
    "bottom": {
      "images": 11,
      "recall": 1.0
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
