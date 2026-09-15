# p_cls_resnet18_384_include_difficult

- 状态：`完成`
- 类型：`classifier`
- 阶段：`pilot`
- difficult 策略：`include_difficult`
- 输入尺寸：`384`
- 计划轮数：`30`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\p_cls_resnet18_384_include_difficult\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.9706 | 0.7500 | 0.8462 | 0.1692 | 33/11/54/1 | 0.9602 | 0.9251 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "p_cls_resnet18_384_include_difficult",
  "kind": "classifier",
  "family": "resnet18",
  "imgsz": 384,
  "difficult_policy": "include_difficult",
  "epochs": 30,
  "stage": "pilot",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\p_cls_resnet18_384_include_difficult\\best.pt",
  "tta": "none",
  "temperature": 0.95,
  "operating_points": {
    "0.1": {
      "threshold": 0.6116509811335797,
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
      "threshold": 0.3579164325298452,
      "recall": 0.9705882352941176,
      "precision": 0.75,
      "f1": 0.846153846153846,
      "fpr": 0.16923076923076924,
      "specificity": 0.8307692307692307,
      "tp": 33,
      "fp": 11,
      "tn": 54,
      "fn": 1
    },
    "0.3": {
      "threshold": 0.3579164325298452,
      "recall": 0.9705882352941176,
      "precision": 0.75,
      "f1": 0.846153846153846,
      "fpr": 0.16923076923076924,
      "specificity": 0.8307692307692307,
      "tp": 33,
      "fp": 11,
      "tn": 54,
      "fn": 1
    },
    "0.5": {
      "threshold": 0.1442438116454042,
      "recall": 1.0,
      "precision": 0.576271186440678,
      "f1": 0.7311827956989247,
      "fpr": 0.38461538461538464,
      "specificity": 0.6153846153846154,
      "tp": 34,
      "fp": 25,
      "tn": 40,
      "fn": 0
    }
  },
  "primary": {
    "threshold": 0.3579164325298452,
    "recall": 0.9705882352941176,
    "precision": 0.75,
    "f1": 0.846153846153846,
    "fpr": 0.16923076923076924,
    "specificity": 0.8307692307692307,
    "tp": 33,
    "fp": 11,
    "tn": 54,
    "fn": 1
  },
  "auroc": 0.9601809954751132,
  "auprc": 0.9250929066421876,
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
