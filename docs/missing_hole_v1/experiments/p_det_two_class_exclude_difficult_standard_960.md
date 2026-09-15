# p_det_two_class_exclude_difficult_standard_960

- 状态：`完成`
- 类型：`detector`
- 阶段：`pilot`
- difficult 策略：`exclude_difficult`
- 输入尺寸：`960`
- 计划轮数：`35`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\p_det_two_class_exclude_difficult_standard_960\weights\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.9412 | 0.8649 | 0.9014 | 0.0769 | 32/5/60/2 | 0.9656 | 0.9571 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "p_det_two_class_exclude_difficult_standard_960",
  "kind": "detector",
  "scheme": "two_class",
  "difficult_policy": "exclude_difficult",
  "architecture": "standard",
  "imgsz": 960,
  "epochs": 35,
  "stage": "pilot",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\p_det_two_class_exclude_difficult_standard_960\\weights\\best.pt",
  "tta": "none",
  "temperature": 1.6999999999999997,
  "operating_points": {
    "0.1": {
      "threshold": 0.15050156702657683,
      "recall": 0.9411764705882353,
      "precision": 0.8648648648648649,
      "f1": 0.9014084507042254,
      "fpr": 0.07692307692307693,
      "specificity": 0.9230769230769231,
      "tp": 32,
      "fp": 5,
      "tn": 60,
      "fn": 2
    },
    "0.2": {
      "threshold": 0.15050156702657683,
      "recall": 0.9411764705882353,
      "precision": 0.8648648648648649,
      "f1": 0.9014084507042254,
      "fpr": 0.07692307692307693,
      "specificity": 0.9230769230769231,
      "tp": 32,
      "fp": 5,
      "tn": 60,
      "fn": 2
    },
    "0.3": {
      "threshold": 0.059570393321004146,
      "recall": 0.9705882352941176,
      "precision": 0.6875,
      "f1": 0.8048780487804877,
      "fpr": 0.23076923076923078,
      "specificity": 0.7692307692307692,
      "tp": 33,
      "fp": 15,
      "tn": 50,
      "fn": 1
    },
    "0.5": {
      "threshold": 0.059570393321004146,
      "recall": 0.9705882352941176,
      "precision": 0.6875,
      "f1": 0.8048780487804877,
      "fpr": 0.23076923076923078,
      "specificity": 0.7692307692307692,
      "tp": 33,
      "fp": 15,
      "tn": 50,
      "fn": 1
    }
  },
  "primary": {
    "threshold": 0.15050156702657683,
    "recall": 0.9411764705882353,
    "precision": 0.8648648648648649,
    "f1": 0.9014084507042254,
    "fpr": 0.07692307692307693,
    "specificity": 0.9230769230769231,
    "tp": 32,
    "fp": 5,
    "tn": 60,
    "fn": 2
  },
  "auroc": 0.9656108597285068,
  "auprc": 0.9571235148441032,
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
