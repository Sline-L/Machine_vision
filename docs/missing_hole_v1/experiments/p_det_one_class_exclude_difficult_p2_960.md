# p_det_one_class_exclude_difficult_p2_960

- 状态：`完成`
- 类型：`detector`
- 阶段：`pilot`
- difficult 策略：`exclude_difficult`
- 输入尺寸：`960`
- 计划轮数：`35`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\p_det_one_class_exclude_difficult_p2_960\weights\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.9706 | 0.7174 | 0.8250 | 0.2000 | 33/13/52/1 | 0.9674 | 0.9415 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "p_det_one_class_exclude_difficult_p2_960",
  "kind": "detector",
  "scheme": "one_class",
  "difficult_policy": "exclude_difficult",
  "architecture": "p2",
  "imgsz": 960,
  "epochs": 35,
  "stage": "pilot",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\p_det_one_class_exclude_difficult_p2_960\\weights\\best.pt",
  "tta": "none",
  "temperature": 1.75,
  "operating_points": {
    "0.1": {
      "threshold": 0.2010659442592251,
      "recall": 0.8823529411764706,
      "precision": 0.9090909090909091,
      "f1": 0.8955223880597014,
      "fpr": 0.046153846153846156,
      "specificity": 0.9538461538461538,
      "tp": 30,
      "fp": 3,
      "tn": 62,
      "fn": 4
    },
    "0.2": {
      "threshold": 0.08182442222765104,
      "recall": 0.9705882352941176,
      "precision": 0.717391304347826,
      "f1": 0.825,
      "fpr": 0.2,
      "specificity": 0.8,
      "tp": 33,
      "fp": 13,
      "tn": 52,
      "fn": 1
    },
    "0.3": {
      "threshold": 0.07098190471066129,
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
      "threshold": 0.07098190471066129,
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
    "threshold": 0.08182442222765104,
    "recall": 0.9705882352941176,
    "precision": 0.717391304347826,
    "f1": 0.825,
    "fpr": 0.2,
    "specificity": 0.8,
    "tp": 33,
    "fp": 13,
    "tn": 52,
    "fn": 1
  },
  "auroc": 0.967420814479638,
  "auprc": 0.9414995738828112,
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
