# p_det_two_class_exclude_difficult_p2_960

- 状态：`完成`
- 类型：`detector`
- 阶段：`pilot`
- difficult 策略：`exclude_difficult`
- 输入尺寸：`960`
- 计划轮数：`35`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\p_det_two_class_exclude_difficult_p2_960\weights\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.8824 | 0.8333 | 0.8571 | 0.0923 | 30/6/59/4 | 0.9448 | 0.9205 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "p_det_two_class_exclude_difficult_p2_960",
  "kind": "detector",
  "scheme": "two_class",
  "difficult_policy": "exclude_difficult",
  "architecture": "p2",
  "imgsz": 960,
  "epochs": 35,
  "stage": "pilot",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\p_det_two_class_exclude_difficult_p2_960\\weights\\best.pt",
  "tta": "none",
  "temperature": 2.65,
  "operating_points": {
    "0.1": {
      "threshold": 0.1942490774445301,
      "recall": 0.8823529411764706,
      "precision": 0.8333333333333334,
      "f1": 0.8571428571428571,
      "fpr": 0.09230769230769231,
      "specificity": 0.9076923076923077,
      "tp": 30,
      "fp": 6,
      "tn": 59,
      "fn": 4
    },
    "0.2": {
      "threshold": 0.1942490774445301,
      "recall": 0.8823529411764706,
      "precision": 0.8333333333333334,
      "f1": 0.8571428571428571,
      "fpr": 0.09230769230769231,
      "specificity": 0.9076923076923077,
      "tp": 30,
      "fp": 6,
      "tn": 59,
      "fn": 4
    },
    "0.3": {
      "threshold": 0.12644748265595024,
      "recall": 0.9411764705882353,
      "precision": 0.6530612244897959,
      "f1": 0.7710843373493975,
      "fpr": 0.26153846153846155,
      "specificity": 0.7384615384615385,
      "tp": 32,
      "fp": 17,
      "tn": 48,
      "fn": 2
    },
    "0.5": {
      "threshold": 0.09703032162124489,
      "recall": 1.0,
      "precision": 0.5230769230769231,
      "f1": 0.686868686868687,
      "fpr": 0.47692307692307695,
      "specificity": 0.523076923076923,
      "tp": 34,
      "fp": 31,
      "tn": 34,
      "fn": 0
    }
  },
  "primary": {
    "threshold": 0.1942490774445301,
    "recall": 0.8823529411764706,
    "precision": 0.8333333333333334,
    "f1": 0.8571428571428571,
    "fpr": 0.09230769230769231,
    "specificity": 0.9076923076923077,
    "tp": 30,
    "fp": 6,
    "tn": 59,
    "fn": 4
  },
  "auroc": 0.9447963800904977,
  "auprc": 0.9205453165193401,
  "groups": {
    "bottom": {
      "images": 11,
      "recall": 0.8181818181818182
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
      "recall": 0.3333333333333333
    }
  }
}
```
