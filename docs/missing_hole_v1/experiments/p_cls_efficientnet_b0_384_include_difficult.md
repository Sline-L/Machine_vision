# p_cls_efficientnet_b0_384_include_difficult

- 状态：`完成`
- 类型：`classifier`
- 阶段：`pilot`
- difficult 策略：`include_difficult`
- 输入尺寸：`384`
- 计划轮数：`30`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\p_cls_efficientnet_b0_384_include_difficult\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.9412 | 0.7805 | 0.8533 | 0.1385 | 32/9/56/2 | 0.9308 | 0.8583 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "p_cls_efficientnet_b0_384_include_difficult",
  "kind": "classifier",
  "family": "efficientnet_b0",
  "imgsz": 384,
  "difficult_policy": "include_difficult",
  "epochs": 30,
  "stage": "pilot",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\p_cls_efficientnet_b0_384_include_difficult\\best.pt",
  "tta": "none",
  "temperature": 0.8749999999999999,
  "operating_points": {
    "0.1": {
      "threshold": 0.5114127690096795,
      "recall": 0.9117647058823529,
      "precision": 0.8378378378378378,
      "f1": 0.8732394366197184,
      "fpr": 0.09230769230769231,
      "specificity": 0.9076923076923077,
      "tp": 31,
      "fp": 6,
      "tn": 59,
      "fn": 3
    },
    "0.2": {
      "threshold": 0.4233365024309141,
      "recall": 0.9411764705882353,
      "precision": 0.7804878048780488,
      "f1": 0.8533333333333334,
      "fpr": 0.13846153846153847,
      "specificity": 0.8615384615384616,
      "tp": 32,
      "fp": 9,
      "tn": 56,
      "fn": 2
    },
    "0.3": {
      "threshold": 0.4233365024309141,
      "recall": 0.9411764705882353,
      "precision": 0.7804878048780488,
      "f1": 0.8533333333333334,
      "fpr": 0.13846153846153847,
      "specificity": 0.8615384615384616,
      "tp": 32,
      "fp": 9,
      "tn": 56,
      "fn": 2
    },
    "0.5": {
      "threshold": 0.4233365024309141,
      "recall": 0.9411764705882353,
      "precision": 0.7804878048780488,
      "f1": 0.8533333333333334,
      "fpr": 0.13846153846153847,
      "specificity": 0.8615384615384616,
      "tp": 32,
      "fp": 9,
      "tn": 56,
      "fn": 2
    }
  },
  "primary": {
    "threshold": 0.4233365024309141,
    "recall": 0.9411764705882353,
    "precision": 0.7804878048780488,
    "f1": 0.8533333333333334,
    "fpr": 0.13846153846153847,
    "specificity": 0.8615384615384616,
    "tp": 32,
    "fp": 9,
    "tn": 56,
    "fn": 2
  },
  "auroc": 0.9307692307692308,
  "auprc": 0.8583244359842928,
  "groups": {
    "bottom": {
      "images": 11,
      "recall": 0.8181818181818182
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
