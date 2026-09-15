# p_det_three_class_include_difficult_standard_960

- 状态：`完成`
- 类型：`detector`
- 阶段：`pilot`
- difficult 策略：`include_difficult`
- 输入尺寸：`960`
- 计划轮数：`35`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\p_det_three_class_include_difficult_standard_960\weights\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.9118 | 0.7949 | 0.8493 | 0.1231 | 31/8/57/3 | 0.9683 | 0.9506 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "p_det_three_class_include_difficult_standard_960",
  "kind": "detector",
  "scheme": "three_class",
  "difficult_policy": "include_difficult",
  "architecture": "standard",
  "imgsz": 960,
  "epochs": 35,
  "stage": "pilot",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\p_det_three_class_include_difficult_standard_960\\weights\\best.pt",
  "tta": "none",
  "temperature": 1.475,
  "operating_points": {
    "0.1": {
      "threshold": 0.19107015018611115,
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
      "threshold": 0.1459452891769405,
      "recall": 0.9117647058823529,
      "precision": 0.7948717948717948,
      "f1": 0.8493150684931507,
      "fpr": 0.12307692307692308,
      "specificity": 0.8769230769230769,
      "tp": 31,
      "fp": 8,
      "tn": 57,
      "fn": 3
    },
    "0.3": {
      "threshold": 0.052484389493964466,
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
      "threshold": 0.052484389493964466,
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
    "threshold": 0.1459452891769405,
    "recall": 0.9117647058823529,
    "precision": 0.7948717948717948,
    "f1": 0.8493150684931507,
    "fpr": 0.12307692307692308,
    "specificity": 0.8769230769230769,
    "tp": 31,
    "fp": 8,
    "tn": 57,
    "fn": 3
  },
  "auroc": 0.9683257918552036,
  "auprc": 0.9506245460906458,
  "groups": {
    "bottom": {
      "images": 11,
      "recall": 0.8181818181818182
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
      "recall": 0.3333333333333333
    }
  }
}
```
