# p_cls_yolo_cls_512_include_difficult

- 状态：`完成`
- 类型：`classifier`
- 阶段：`pilot`
- difficult 策略：`include_difficult`
- 输入尺寸：`512`
- 计划轮数：`30`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\p_cls_yolo_cls_512_include_difficult\weights\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.6765 | 0.6970 | 0.6866 | 0.1538 | 23/10/55/11 | 0.8385 | 0.7300 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "p_cls_yolo_cls_512_include_difficult",
  "kind": "classifier",
  "family": "yolo_cls",
  "imgsz": 512,
  "difficult_policy": "include_difficult",
  "epochs": 30,
  "stage": "pilot",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\p_cls_yolo_cls_512_include_difficult\\weights\\best.pt",
  "tta": "flip",
  "temperature": 4.0,
  "operating_points": {
    "0.1": {
      "threshold": 0.8056875685336025,
      "recall": 0.47058823529411764,
      "precision": 0.7619047619047619,
      "f1": 0.5818181818181817,
      "fpr": 0.07692307692307693,
      "specificity": 0.9230769230769231,
      "tp": 16,
      "fp": 5,
      "tn": 60,
      "fn": 18
    },
    "0.2": {
      "threshold": 0.7339350295400944,
      "recall": 0.6764705882352942,
      "precision": 0.696969696969697,
      "f1": 0.6865671641791046,
      "fpr": 0.15384615384615385,
      "specificity": 0.8461538461538461,
      "tp": 23,
      "fp": 10,
      "tn": 55,
      "fn": 11
    },
    "0.3": {
      "threshold": 0.667195919887456,
      "recall": 0.7352941176470589,
      "precision": 0.5813953488372093,
      "f1": 0.6493506493506493,
      "fpr": 0.27692307692307694,
      "specificity": 0.7230769230769231,
      "tp": 25,
      "fp": 18,
      "tn": 47,
      "fn": 9
    },
    "0.5": {
      "threshold": 0.5644085576153905,
      "recall": 0.9411764705882353,
      "precision": 0.5245901639344263,
      "f1": 0.6736842105263159,
      "fpr": 0.4461538461538462,
      "specificity": 0.5538461538461539,
      "tp": 32,
      "fp": 29,
      "tn": 36,
      "fn": 2
    }
  },
  "primary": {
    "threshold": 0.7339350295400944,
    "recall": 0.6764705882352942,
    "precision": 0.696969696969697,
    "f1": 0.6865671641791046,
    "fpr": 0.15384615384615385,
    "specificity": 0.8461538461538461,
    "tp": 23,
    "fp": 10,
    "tn": 55,
    "fn": 11
  },
  "auroc": 0.8384615384615385,
  "auprc": 0.7300156181191517,
  "groups": {
    "bottom": {
      "images": 11,
      "recall": 0.5454545454545454
    },
    "oblique": {
      "images": 12,
      "recall": 0.5833333333333334
    },
    "side": {
      "images": 14,
      "recall": 0.9285714285714286
    },
    "difficult": {
      "images": 3,
      "recall": 0.3333333333333333
    }
  }
}
```
