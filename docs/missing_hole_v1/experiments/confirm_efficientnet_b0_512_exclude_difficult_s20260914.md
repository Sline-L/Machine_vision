# confirm_efficientnet_b0_512_exclude_difficult_s20260914

- 状态：`完成`
- 类型：`classifier`
- 阶段：`confirmation`
- difficult 策略：`exclude_difficult`
- 输入尺寸：`512`
- 计划轮数：`100`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\confirm_efficientnet_b0_512_exclude_difficult_s20260914\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 1.0000 | 0.8095 | 0.8947 | 0.1231 | 34/8/57/0 | 0.9579 | 0.8609 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "confirm_efficientnet_b0_512_exclude_difficult_s20260914",
  "kind": "classifier",
  "family": "efficientnet_b0",
  "imgsz": 512,
  "difficult_policy": "exclude_difficult",
  "epochs": 100,
  "stage": "confirmation",
  "seed": 20260914,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\confirm_efficientnet_b0_512_exclude_difficult_s20260914\\best.pt",
  "tta": "none",
  "temperature": 1.4499999999999997,
  "operating_points": {
    "0.1": {
      "threshold": 0.8407338757937709,
      "recall": 0.7941176470588235,
      "precision": 0.9,
      "f1": 0.84375,
      "fpr": 0.046153846153846156,
      "specificity": 0.9538461538461538,
      "tp": 27,
      "fp": 3,
      "tn": 62,
      "fn": 7
    },
    "0.2": {
      "threshold": 0.3368245372322089,
      "recall": 1.0,
      "precision": 0.8095238095238095,
      "f1": 0.8947368421052632,
      "fpr": 0.12307692307692308,
      "specificity": 0.8769230769230769,
      "tp": 34,
      "fp": 8,
      "tn": 57,
      "fn": 0
    },
    "0.3": {
      "threshold": 0.3368245372322089,
      "recall": 1.0,
      "precision": 0.8095238095238095,
      "f1": 0.8947368421052632,
      "fpr": 0.12307692307692308,
      "specificity": 0.8769230769230769,
      "tp": 34,
      "fp": 8,
      "tn": 57,
      "fn": 0
    },
    "0.5": {
      "threshold": 0.3368245372322089,
      "recall": 1.0,
      "precision": 0.8095238095238095,
      "f1": 0.8947368421052632,
      "fpr": 0.12307692307692308,
      "specificity": 0.8769230769230769,
      "tp": 34,
      "fp": 8,
      "tn": 57,
      "fn": 0
    }
  },
  "primary": {
    "threshold": 0.3368245372322089,
    "recall": 1.0,
    "precision": 0.8095238095238095,
    "f1": 0.8947368421052632,
    "fpr": 0.12307692307692308,
    "specificity": 0.8769230769230769,
    "tp": 34,
    "fp": 8,
    "tn": 57,
    "fn": 0
  },
  "auroc": 0.9579185520361991,
  "auprc": 0.8609205199446808,
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
