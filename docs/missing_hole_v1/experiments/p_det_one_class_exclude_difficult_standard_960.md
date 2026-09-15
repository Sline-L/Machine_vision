# p_det_one_class_exclude_difficult_standard_960

- 状态：`完成`
- 类型：`detector`
- 阶段：`pilot`
- difficult 策略：`exclude_difficult`
- 输入尺寸：`960`
- 计划轮数：`35`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\p_det_one_class_exclude_difficult_standard_960\weights\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.9706 | 0.8462 | 0.9041 | 0.0923 | 33/6/59/1 | 0.9742 | 0.9447 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "p_det_one_class_exclude_difficult_standard_960",
  "kind": "detector",
  "scheme": "one_class",
  "difficult_policy": "exclude_difficult",
  "architecture": "standard",
  "imgsz": 960,
  "epochs": 35,
  "stage": "pilot",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\p_det_one_class_exclude_difficult_standard_960\\weights\\best.pt",
  "tta": "none",
  "temperature": 1.8499999999999996,
  "operating_points": {
    "0.1": {
      "threshold": 0.12059450038989711,
      "recall": 0.9705882352941176,
      "precision": 0.8461538461538461,
      "f1": 0.9041095890410958,
      "fpr": 0.09230769230769231,
      "specificity": 0.9076923076923077,
      "tp": 33,
      "fp": 6,
      "tn": 59,
      "fn": 1
    },
    "0.2": {
      "threshold": 0.12059450038989711,
      "recall": 0.9705882352941176,
      "precision": 0.8461538461538461,
      "f1": 0.9041095890410958,
      "fpr": 0.09230769230769231,
      "specificity": 0.9076923076923077,
      "tp": 33,
      "fp": 6,
      "tn": 59,
      "fn": 1
    },
    "0.3": {
      "threshold": 0.06173486998770686,
      "recall": 1.0,
      "precision": 0.6938775510204082,
      "f1": 0.819277108433735,
      "fpr": 0.23076923076923078,
      "specificity": 0.7692307692307692,
      "tp": 34,
      "fp": 15,
      "tn": 50,
      "fn": 0
    },
    "0.5": {
      "threshold": 0.06173486998770686,
      "recall": 1.0,
      "precision": 0.6938775510204082,
      "f1": 0.819277108433735,
      "fpr": 0.23076923076923078,
      "specificity": 0.7692307692307692,
      "tp": 34,
      "fp": 15,
      "tn": 50,
      "fn": 0
    }
  },
  "primary": {
    "threshold": 0.12059450038989711,
    "recall": 0.9705882352941176,
    "precision": 0.8461538461538461,
    "f1": 0.9041095890410958,
    "fpr": 0.09230769230769231,
    "specificity": 0.9076923076923077,
    "tp": 33,
    "fp": 6,
    "tn": 59,
    "fn": 1
  },
  "auroc": 0.9742081447963801,
  "auprc": 0.9447332702427802,
  "groups": {
    "bottom": {
      "images": 11,
      "recall": 1.0
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
      "recall": 1.0
    }
  }
}
```
