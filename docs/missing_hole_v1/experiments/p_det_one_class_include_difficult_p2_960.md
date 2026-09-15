# p_det_one_class_include_difficult_p2_960

- 状态：`完成`
- 类型：`detector`
- 阶段：`pilot`
- difficult 策略：`include_difficult`
- 输入尺寸：`960`
- 计划轮数：`35`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\p_det_one_class_include_difficult_p2_960\weights\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.8824 | 0.7895 | 0.8333 | 0.1231 | 30/8/57/4 | 0.9624 | 0.9450 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "p_det_one_class_include_difficult_p2_960",
  "kind": "detector",
  "scheme": "one_class",
  "difficult_policy": "include_difficult",
  "architecture": "p2",
  "imgsz": 960,
  "epochs": 35,
  "stage": "pilot",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\p_det_one_class_include_difficult_p2_960\\weights\\best.pt",
  "tta": "none",
  "temperature": 1.6999999999999997,
  "operating_points": {
    "0.1": {
      "threshold": 0.19830491434553987,
      "recall": 0.8529411764705882,
      "precision": 0.90625,
      "f1": 0.8787878787878787,
      "fpr": 0.046153846153846156,
      "specificity": 0.9538461538461538,
      "tp": 29,
      "fp": 3,
      "tn": 62,
      "fn": 5
    },
    "0.2": {
      "threshold": 0.15523832551409522,
      "recall": 0.8823529411764706,
      "precision": 0.7894736842105263,
      "f1": 0.8333333333333333,
      "fpr": 0.12307692307692308,
      "specificity": 0.8769230769230769,
      "tp": 30,
      "fp": 8,
      "tn": 57,
      "fn": 4
    },
    "0.3": {
      "threshold": 0.1042594154354084,
      "recall": 0.9705882352941176,
      "precision": 0.6875,
      "f1": 0.8048780487804877,
      "fpr": 0.23076923076923078,
      "specificity": 0.7692307692307692,
      "tp": 33,
      "fp": 15,
      "tn": 50,
      "fn": 1
    },
    "0.5": {
      "threshold": 0.08328339415493502,
      "recall": 1.0,
      "precision": 0.6181818181818182,
      "f1": 0.7640449438202247,
      "fpr": 0.3230769230769231,
      "specificity": 0.676923076923077,
      "tp": 34,
      "fp": 21,
      "tn": 44,
      "fn": 0
    }
  },
  "primary": {
    "threshold": 0.15523832551409522,
    "recall": 0.8823529411764706,
    "precision": 0.7894736842105263,
    "f1": 0.8333333333333333,
    "fpr": 0.12307692307692308,
    "specificity": 0.8769230769230769,
    "tp": 30,
    "fp": 8,
    "tn": 57,
    "fn": 4
  },
  "auroc": 0.9624434389140272,
  "auprc": 0.9449649212705934,
  "groups": {
    "bottom": {
      "images": 11,
      "recall": 0.9090909090909091
    },
    "oblique": {
      "images": 12,
      "recall": 0.8333333333333334
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
