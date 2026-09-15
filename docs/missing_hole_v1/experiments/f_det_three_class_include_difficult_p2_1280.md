# f_det_three_class_include_difficult_p2_1280

- 状态：`完成`
- 类型：`detector`
- 阶段：`full`
- difficult 策略：`include_difficult`
- 输入尺寸：`1280`
- 计划轮数：`100`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\f_det_three_class_include_difficult_p2_1280\weights\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.9412 | 0.7273 | 0.8205 | 0.1846 | 32/12/53/2 | 0.9484 | 0.9232 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "f_det_three_class_include_difficult_p2_1280",
  "kind": "detector",
  "scheme": "three_class",
  "difficult_policy": "include_difficult",
  "architecture": "p2",
  "imgsz": 1280,
  "epochs": 100,
  "stage": "full",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\f_det_three_class_include_difficult_p2_1280\\weights\\best.pt",
  "tta": "none",
  "temperature": 3.0749999999999997,
  "operating_points": {
    "0.1": {
      "threshold": 0.28950245232697525,
      "recall": 0.9117647058823529,
      "precision": 0.9117647058823529,
      "f1": 0.9117647058823528,
      "fpr": 0.046153846153846156,
      "specificity": 0.9538461538461538,
      "tp": 31,
      "fp": 3,
      "tn": 62,
      "fn": 3
    },
    "0.2": {
      "threshold": 0.1503717105645539,
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
      "threshold": 0.1503717105645539,
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
    "0.5": {
      "threshold": 0.1503717105645539,
      "recall": 0.9411764705882353,
      "precision": 0.7272727272727273,
      "f1": 0.8205128205128205,
      "fpr": 0.18461538461538463,
      "specificity": 0.8153846153846154,
      "tp": 32,
      "fp": 12,
      "tn": 53,
      "fn": 2
    }
  },
  "primary": {
    "threshold": 0.1503717105645539,
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
  "auroc": 0.9484162895927601,
  "auprc": 0.9231850323919306,
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
