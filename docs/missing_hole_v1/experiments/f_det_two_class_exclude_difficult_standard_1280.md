# f_det_two_class_exclude_difficult_standard_1280

- 状态：`完成`
- 类型：`detector`
- 阶段：`full`
- difficult 策略：`exclude_difficult`
- 输入尺寸：`1280`
- 计划轮数：`100`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\f_det_two_class_exclude_difficult_standard_1280\weights\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.9412 | 0.7273 | 0.8205 | 0.1846 | 32/12/53/2 | 0.9638 | 0.9480 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "f_det_two_class_exclude_difficult_standard_1280",
  "kind": "detector",
  "scheme": "two_class",
  "difficult_policy": "exclude_difficult",
  "architecture": "standard",
  "imgsz": 1280,
  "epochs": 100,
  "stage": "full",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\f_det_two_class_exclude_difficult_standard_1280\\weights\\best.pt",
  "tta": "none",
  "temperature": 2.55,
  "operating_points": {
    "0.1": {
      "threshold": 0.28781822166178034,
      "recall": 0.8823529411764706,
      "precision": 0.8571428571428571,
      "f1": 0.8695652173913043,
      "fpr": 0.07692307692307693,
      "specificity": 0.9230769230769231,
      "tp": 30,
      "fp": 5,
      "tn": 60,
      "fn": 4
    },
    "0.2": {
      "threshold": 0.14237709686619268,
      "recall": 0.9411764705882353,
      "precision": 0.7272727272727273,
      "f1": 0.8205128205128205,
      "fpr": 0.18461538461538463,
      "specificity": 0.8153846153846154,
      "tp": 32,
      "fp": 12,
      "tn": 53,
      "fn": 2
    },
    "0.3": {
      "threshold": 0.10576813299237212,
      "recall": 0.9705882352941176,
      "precision": 0.7021276595744681,
      "f1": 0.8148148148148149,
      "fpr": 0.2153846153846154,
      "specificity": 0.7846153846153846,
      "tp": 33,
      "fp": 14,
      "tn": 51,
      "fn": 1
    },
    "0.5": {
      "threshold": 0.10576813299237212,
      "recall": 0.9705882352941176,
      "precision": 0.7021276595744681,
      "f1": 0.8148148148148149,
      "fpr": 0.2153846153846154,
      "specificity": 0.7846153846153846,
      "tp": 33,
      "fp": 14,
      "tn": 51,
      "fn": 1
    }
  },
  "primary": {
    "threshold": 0.14237709686619268,
    "recall": 0.9411764705882353,
    "precision": 0.7272727272727273,
    "f1": 0.8205128205128205,
    "fpr": 0.18461538461538463,
    "specificity": 0.8153846153846154,
    "tp": 32,
    "fp": 12,
    "tn": 53,
    "fn": 2
  },
  "auroc": 0.9638009049773756,
  "auprc": 0.9479972565618686,
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
      "recall": 0.3333333333333333
    }
  }
}
```
