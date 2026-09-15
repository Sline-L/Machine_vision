# p_cls_efficientnet_b0_512_exclude_difficult

- 状态：`完成`
- 类型：`classifier`
- 阶段：`pilot`
- difficult 策略：`exclude_difficult`
- 输入尺寸：`512`
- 计划轮数：`30`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\p_cls_efficientnet_b0_512_exclude_difficult\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.9706 | 0.7174 | 0.8250 | 0.2000 | 33/13/52/1 | 0.9575 | 0.9140 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "p_cls_efficientnet_b0_512_exclude_difficult",
  "kind": "classifier",
  "family": "efficientnet_b0",
  "imgsz": 512,
  "difficult_policy": "exclude_difficult",
  "epochs": 30,
  "stage": "pilot",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\p_cls_efficientnet_b0_512_exclude_difficult\\best.pt",
  "tta": "none",
  "temperature": 0.95,
  "operating_points": {
    "0.1": {
      "threshold": 0.600002020422674,
      "recall": 0.8529411764705882,
      "precision": 0.8285714285714286,
      "f1": 0.8405797101449276,
      "fpr": 0.09230769230769231,
      "specificity": 0.9076923076923077,
      "tp": 29,
      "fp": 6,
      "tn": 59,
      "fn": 5
    },
    "0.2": {
      "threshold": 0.30399580230145806,
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
      "threshold": 0.2987436616553831,
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
      "threshold": 0.2987436616553831,
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
    "threshold": 0.30399580230145806,
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
  "auroc": 0.9574660633484163,
  "auprc": 0.9140453004774415,
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
      "recall": 0.9285714285714286
    },
    "difficult": {
      "images": 3,
      "recall": 1.0
    }
  }
}
```
