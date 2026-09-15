# f_det_three_class_include_difficult_p2_960

- 状态：`完成`
- 类型：`detector`
- 阶段：`full`
- difficult 策略：`include_difficult`
- 输入尺寸：`960`
- 计划轮数：`100`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\f_det_three_class_include_difficult_p2_960\weights\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.9412 | 0.8421 | 0.8889 | 0.0923 | 32/6/59/2 | 0.9434 | 0.9240 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "f_det_three_class_include_difficult_p2_960",
  "kind": "detector",
  "scheme": "three_class",
  "difficult_policy": "include_difficult",
  "architecture": "p2",
  "imgsz": 960,
  "epochs": 100,
  "stage": "full",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\f_det_three_class_include_difficult_p2_960\\weights\\best.pt",
  "tta": "none",
  "temperature": 3.4,
  "operating_points": {
    "0.1": {
      "threshold": 0.2811083152039577,
      "recall": 0.9411764705882353,
      "precision": 0.8421052631578947,
      "f1": 0.8888888888888888,
      "fpr": 0.09230769230769231,
      "specificity": 0.9076923076923077,
      "tp": 32,
      "fp": 6,
      "tn": 59,
      "fn": 2
    },
    "0.2": {
      "threshold": 0.2811083152039577,
      "recall": 0.9411764705882353,
      "precision": 0.8421052631578947,
      "f1": 0.8888888888888888,
      "fpr": 0.09230769230769231,
      "specificity": 0.9076923076923077,
      "tp": 32,
      "fp": 6,
      "tn": 59,
      "fn": 2
    },
    "0.3": {
      "threshold": 0.2811083152039577,
      "recall": 0.9411764705882353,
      "precision": 0.8421052631578947,
      "f1": 0.8888888888888888,
      "fpr": 0.09230769230769231,
      "specificity": 0.9076923076923077,
      "tp": 32,
      "fp": 6,
      "tn": 59,
      "fn": 2
    },
    "0.5": {
      "threshold": 0.2811083152039577,
      "recall": 0.9411764705882353,
      "precision": 0.8421052631578947,
      "f1": 0.8888888888888888,
      "fpr": 0.09230769230769231,
      "specificity": 0.9076923076923077,
      "tp": 32,
      "fp": 6,
      "tn": 59,
      "fn": 2
    }
  },
  "primary": {
    "threshold": 0.2811083152039577,
    "recall": 0.9411764705882353,
    "precision": 0.8421052631578947,
    "f1": 0.8888888888888888,
    "fpr": 0.09230769230769231,
    "specificity": 0.9076923076923077,
    "tp": 32,
    "fp": 6,
    "tn": 59,
    "fn": 2
  },
  "auroc": 0.9434389140271493,
  "auprc": 0.9240156822713502,
  "groups": {
    "bottom": {
      "images": 11,
      "recall": 0.9090909090909091
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
      "recall": 0.6666666666666666
    }
  }
}
```
