# f_det_one_class_exclude_difficult_standard_960

- 状态：`完成`
- 类型：`detector`
- 阶段：`full`
- difficult 策略：`exclude_difficult`
- 输入尺寸：`960`
- 计划轮数：`100`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\f_det_one_class_exclude_difficult_standard_960\weights\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.9706 | 0.8462 | 0.9041 | 0.0923 | 33/6/59/1 | 0.9783 | 0.9709 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "f_det_one_class_exclude_difficult_standard_960",
  "kind": "detector",
  "scheme": "one_class",
  "difficult_policy": "exclude_difficult",
  "architecture": "standard",
  "imgsz": 960,
  "epochs": 100,
  "stage": "full",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\f_det_one_class_exclude_difficult_standard_960\\weights\\best.pt",
  "tta": "none",
  "temperature": 2.85,
  "operating_points": {
    "0.1": {
      "threshold": 0.17185511647094928,
      "recall": 0.9705882352941176,
      "precision": 0.8461538461538461,
      "f1": 0.9041095890410958,
      "fpr": 0.09230769230769231,
      "specificity": 0.9076923076923077,
      "tp": 33,
      "fp": 6,
      "tn": 59,
      "fn": 1
    },
    "0.2": {
      "threshold": 0.17185511647094928,
      "recall": 0.9705882352941176,
      "precision": 0.8461538461538461,
      "f1": 0.9041095890410958,
      "fpr": 0.09230769230769231,
      "specificity": 0.9076923076923077,
      "tp": 33,
      "fp": 6,
      "tn": 59,
      "fn": 1
    },
    "0.3": {
      "threshold": 0.17185511647094928,
      "recall": 0.9705882352941176,
      "precision": 0.8461538461538461,
      "f1": 0.9041095890410958,
      "fpr": 0.09230769230769231,
      "specificity": 0.9076923076923077,
      "tp": 33,
      "fp": 6,
      "tn": 59,
      "fn": 1
    },
    "0.5": {
      "threshold": 0.17185511647094928,
      "recall": 0.9705882352941176,
      "precision": 0.8461538461538461,
      "f1": 0.9041095890410958,
      "fpr": 0.09230769230769231,
      "specificity": 0.9076923076923077,
      "tp": 33,
      "fp": 6,
      "tn": 59,
      "fn": 1
    }
  },
  "primary": {
    "threshold": 0.17185511647094928,
    "recall": 0.9705882352941176,
    "precision": 0.8461538461538461,
    "f1": 0.9041095890410958,
    "fpr": 0.09230769230769231,
    "specificity": 0.9076923076923077,
    "tp": 33,
    "fp": 6,
    "tn": 59,
    "fn": 1
  },
  "auroc": 0.9782805429864253,
  "auprc": 0.9709462680050917,
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
