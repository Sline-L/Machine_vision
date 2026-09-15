# p_cls_efficientnet_b0_384_exclude_difficult

- 状态：`完成`
- 类型：`classifier`
- 阶段：`pilot`
- difficult 策略：`exclude_difficult`
- 输入尺寸：`384`
- 计划轮数：`30`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\p_cls_efficientnet_b0_384_exclude_difficult\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.9706 | 0.7333 | 0.8354 | 0.1846 | 33/12/53/1 | 0.9516 | 0.8614 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "p_cls_efficientnet_b0_384_exclude_difficult",
  "kind": "classifier",
  "family": "efficientnet_b0",
  "imgsz": 384,
  "difficult_policy": "exclude_difficult",
  "epochs": 30,
  "stage": "pilot",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\p_cls_efficientnet_b0_384_exclude_difficult\\best.pt",
  "tta": "none",
  "temperature": 0.8499999999999999,
  "operating_points": {
    "0.1": {
      "threshold": 0.5444058000048086,
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
      "threshold": 0.4043734568418735,
      "recall": 0.9705882352941176,
      "precision": 0.7333333333333333,
      "f1": 0.8354430379746834,
      "fpr": 0.18461538461538463,
      "specificity": 0.8153846153846154,
      "tp": 33,
      "fp": 12,
      "tn": 53,
      "fn": 1
    },
    "0.3": {
      "threshold": 0.37430301129146054,
      "recall": 1.0,
      "precision": 0.7083333333333334,
      "f1": 0.8292682926829268,
      "fpr": 0.2153846153846154,
      "specificity": 0.7846153846153846,
      "tp": 34,
      "fp": 14,
      "tn": 51,
      "fn": 0
    },
    "0.5": {
      "threshold": 0.37430301129146054,
      "recall": 1.0,
      "precision": 0.7083333333333334,
      "f1": 0.8292682926829268,
      "fpr": 0.2153846153846154,
      "specificity": 0.7846153846153846,
      "tp": 34,
      "fp": 14,
      "tn": 51,
      "fn": 0
    }
  },
  "primary": {
    "threshold": 0.4043734568418735,
    "recall": 0.9705882352941176,
    "precision": 0.7333333333333333,
    "f1": 0.8354430379746834,
    "fpr": 0.18461538461538463,
    "specificity": 0.8153846153846154,
    "tp": 33,
    "fp": 12,
    "tn": 53,
    "fn": 1
  },
  "auroc": 0.9515837104072398,
  "auprc": 0.8614098542225607,
  "groups": {
    "bottom": {
      "images": 11,
      "recall": 0.9090909090909091
    },
    "oblique": {
      "images": 12,
      "recall": 1.0
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
