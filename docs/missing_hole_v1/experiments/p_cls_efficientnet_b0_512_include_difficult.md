# p_cls_efficientnet_b0_512_include_difficult

- 状态：`完成`
- 类型：`classifier`
- 阶段：`pilot`
- difficult 策略：`include_difficult`
- 输入尺寸：`512`
- 计划轮数：`30`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\p_cls_efficientnet_b0_512_include_difficult\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.9706 | 0.8049 | 0.8800 | 0.1231 | 33/8/57/1 | 0.9452 | 0.8579 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "p_cls_efficientnet_b0_512_include_difficult",
  "kind": "classifier",
  "family": "efficientnet_b0",
  "imgsz": 512,
  "difficult_policy": "include_difficult",
  "epochs": 30,
  "stage": "pilot",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\p_cls_efficientnet_b0_512_include_difficult\\best.pt",
  "tta": "none",
  "temperature": 1.6749999999999998,
  "operating_points": {
    "0.1": {
      "threshold": 0.6586622009411673,
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
      "threshold": 0.6011713009239796,
      "recall": 0.9705882352941176,
      "precision": 0.8048780487804879,
      "f1": 0.8800000000000001,
      "fpr": 0.12307692307692308,
      "specificity": 0.8769230769230769,
      "tp": 33,
      "fp": 8,
      "tn": 57,
      "fn": 1
    },
    "0.3": {
      "threshold": 0.6011713009239796,
      "recall": 0.9705882352941176,
      "precision": 0.8048780487804879,
      "f1": 0.8800000000000001,
      "fpr": 0.12307692307692308,
      "specificity": 0.8769230769230769,
      "tp": 33,
      "fp": 8,
      "tn": 57,
      "fn": 1
    },
    "0.5": {
      "threshold": 0.6011713009239796,
      "recall": 0.9705882352941176,
      "precision": 0.8048780487804879,
      "f1": 0.8800000000000001,
      "fpr": 0.12307692307692308,
      "specificity": 0.8769230769230769,
      "tp": 33,
      "fp": 8,
      "tn": 57,
      "fn": 1
    }
  },
  "primary": {
    "threshold": 0.6011713009239796,
    "recall": 0.9705882352941176,
    "precision": 0.8048780487804879,
    "f1": 0.8800000000000001,
    "fpr": 0.12307692307692308,
    "specificity": 0.8769230769230769,
    "tp": 33,
    "fp": 8,
    "tn": 57,
    "fn": 1
  },
  "auroc": 0.9452488687782805,
  "auprc": 0.8579306132071425,
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
      "recall": 0.6666666666666666
    }
  }
}
```
