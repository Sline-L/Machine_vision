# f_cls_efficientnet_b0_512_exclude_difficult_s20260913

- 状态：`完成`
- 类型：`classifier`
- 阶段：`full`
- difficult 策略：`exclude_difficult`
- 输入尺寸：`512`
- 计划轮数：`100`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\f_cls_efficientnet_b0_512_exclude_difficult_s20260913\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 1.0000 | 0.8500 | 0.9189 | 0.0923 | 34/6/59/0 | 0.9701 | 0.9247 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "f_cls_efficientnet_b0_512_exclude_difficult_s20260913",
  "kind": "classifier",
  "family": "efficientnet_b0",
  "imgsz": 512,
  "difficult_policy": "exclude_difficult",
  "epochs": 100,
  "stage": "full",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\f_cls_efficientnet_b0_512_exclude_difficult_s20260913\\best.pt",
  "tta": "none",
  "temperature": 0.9999999999999999,
  "operating_points": {
    "0.1": {
      "threshold": 0.3809993863105774,
      "recall": 1.0,
      "precision": 0.85,
      "f1": 0.9189189189189189,
      "fpr": 0.09230769230769231,
      "specificity": 0.9076923076923077,
      "tp": 34,
      "fp": 6,
      "tn": 59,
      "fn": 0
    },
    "0.2": {
      "threshold": 0.3809993863105774,
      "recall": 1.0,
      "precision": 0.85,
      "f1": 0.9189189189189189,
      "fpr": 0.09230769230769231,
      "specificity": 0.9076923076923077,
      "tp": 34,
      "fp": 6,
      "tn": 59,
      "fn": 0
    },
    "0.3": {
      "threshold": 0.3809993863105774,
      "recall": 1.0,
      "precision": 0.85,
      "f1": 0.9189189189189189,
      "fpr": 0.09230769230769231,
      "specificity": 0.9076923076923077,
      "tp": 34,
      "fp": 6,
      "tn": 59,
      "fn": 0
    },
    "0.5": {
      "threshold": 0.3809993863105774,
      "recall": 1.0,
      "precision": 0.85,
      "f1": 0.9189189189189189,
      "fpr": 0.09230769230769231,
      "specificity": 0.9076923076923077,
      "tp": 34,
      "fp": 6,
      "tn": 59,
      "fn": 0
    }
  },
  "primary": {
    "threshold": 0.3809993863105774,
    "recall": 1.0,
    "precision": 0.85,
    "f1": 0.9189189189189189,
    "fpr": 0.09230769230769231,
    "specificity": 0.9076923076923077,
    "tp": 34,
    "fp": 6,
    "tn": 59,
    "fn": 0
  },
  "auroc": 0.9701357466063348,
  "auprc": 0.9247403869240186,
  "groups": {
    "bottom": {
      "images": 11,
      "recall": 1.0
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
