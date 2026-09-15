# f_det_two_class_exclude_difficult_standard_960

- 状态：`完成`
- 类型：`detector`
- 阶段：`full`
- difficult 策略：`exclude_difficult`
- 输入尺寸：`960`
- 计划轮数：`100`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\f_det_two_class_exclude_difficult_standard_960\weights\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.9118 | 0.8378 | 0.8732 | 0.0923 | 31/6/59/3 | 0.9434 | 0.9054 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "f_det_two_class_exclude_difficult_standard_960",
  "kind": "detector",
  "scheme": "two_class",
  "difficult_policy": "exclude_difficult",
  "architecture": "standard",
  "imgsz": 960,
  "epochs": 100,
  "stage": "full",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\f_det_two_class_exclude_difficult_standard_960\\weights\\best.pt",
  "tta": "none",
  "temperature": 2.75,
  "operating_points": {
    "0.1": {
      "threshold": 0.24468774359739287,
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
      "threshold": 0.24468774359739287,
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
    "0.3": {
      "threshold": 0.11759526817964347,
      "recall": 0.9411764705882353,
      "precision": 0.6808510638297872,
      "f1": 0.7901234567901235,
      "fpr": 0.23076923076923078,
      "specificity": 0.7692307692307692,
      "tp": 32,
      "fp": 15,
      "tn": 50,
      "fn": 2
    },
    "0.5": {
      "threshold": 0.08374992051968175,
      "recall": 0.9705882352941176,
      "precision": 0.5689655172413793,
      "f1": 0.717391304347826,
      "fpr": 0.38461538461538464,
      "specificity": 0.6153846153846154,
      "tp": 33,
      "fp": 25,
      "tn": 40,
      "fn": 1
    }
  },
  "primary": {
    "threshold": 0.24468774359739287,
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
  "auroc": 0.9434389140271493,
  "auprc": 0.9054428533242115,
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
