# p_cls_resnet18_384_exclude_difficult

- 状态：`完成`
- 类型：`classifier`
- 阶段：`pilot`
- difficult 策略：`exclude_difficult`
- 输入尺寸：`384`
- 计划轮数：`30`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\p_cls_resnet18_384_exclude_difficult\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.9412 | 0.7442 | 0.8312 | 0.1692 | 32/11/54/2 | 0.9253 | 0.8053 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "p_cls_resnet18_384_exclude_difficult",
  "kind": "classifier",
  "family": "resnet18",
  "imgsz": 384,
  "difficult_policy": "exclude_difficult",
  "epochs": 30,
  "stage": "pilot",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\p_cls_resnet18_384_exclude_difficult\\best.pt",
  "tta": "none",
  "temperature": 2.1999999999999997,
  "operating_points": {
    "0.1": {
      "threshold": 0.6683123700457777,
      "recall": 0.8235294117647058,
      "precision": 0.9032258064516129,
      "f1": 0.8615384615384616,
      "fpr": 0.046153846153846156,
      "specificity": 0.9538461538461538,
      "tp": 28,
      "fp": 3,
      "tn": 62,
      "fn": 6
    },
    "0.2": {
      "threshold": 0.6147663554300913,
      "recall": 0.9411764705882353,
      "precision": 0.7441860465116279,
      "f1": 0.8311688311688312,
      "fpr": 0.16923076923076924,
      "specificity": 0.8307692307692307,
      "tp": 32,
      "fp": 11,
      "tn": 54,
      "fn": 2
    },
    "0.3": {
      "threshold": 0.6147663554300913,
      "recall": 0.9411764705882353,
      "precision": 0.7441860465116279,
      "f1": 0.8311688311688312,
      "fpr": 0.16923076923076924,
      "specificity": 0.8307692307692307,
      "tp": 32,
      "fp": 11,
      "tn": 54,
      "fn": 2
    },
    "0.5": {
      "threshold": 0.571060160725731,
      "recall": 0.9705882352941176,
      "precision": 0.55,
      "f1": 0.7021276595744681,
      "fpr": 0.4153846153846154,
      "specificity": 0.5846153846153845,
      "tp": 33,
      "fp": 27,
      "tn": 38,
      "fn": 1
    }
  },
  "primary": {
    "threshold": 0.6147663554300913,
    "recall": 0.9411764705882353,
    "precision": 0.7441860465116279,
    "f1": 0.8311688311688312,
    "fpr": 0.16923076923076924,
    "specificity": 0.8307692307692307,
    "tp": 32,
    "fp": 11,
    "tn": 54,
    "fn": 2
  },
  "auroc": 0.9253393665158371,
  "auprc": 0.8053085744695121,
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
