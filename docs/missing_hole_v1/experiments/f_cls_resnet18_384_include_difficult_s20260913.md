# f_cls_resnet18_384_include_difficult_s20260913

- 状态：`完成`
- 类型：`classifier`
- 阶段：`full`
- difficult 策略：`include_difficult`
- 输入尺寸：`384`
- 计划轮数：`100`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\f_cls_resnet18_384_include_difficult_s20260913\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 1.0000 | 0.8095 | 0.8947 | 0.1231 | 34/8/57/0 | 0.9638 | 0.8911 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "f_cls_resnet18_384_include_difficult_s20260913",
  "kind": "classifier",
  "family": "resnet18",
  "imgsz": 384,
  "difficult_policy": "include_difficult",
  "epochs": 100,
  "stage": "full",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\f_cls_resnet18_384_include_difficult_s20260913\\best.pt",
  "tta": "none",
  "temperature": 2.375,
  "operating_points": {
    "0.1": {
      "threshold": 0.6516356081146706,
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
      "threshold": 0.6255032716085878,
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
      "threshold": 0.6255032716085878,
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
      "threshold": 0.6255032716085878,
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
    "threshold": 0.6255032716085878,
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
  "auroc": 0.9638009049773756,
  "auprc": 0.8910958434740628,
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
