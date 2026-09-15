# p_cls_yolo_cls_384_include_difficult

- 状态：`完成`
- 类型：`classifier`
- 阶段：`pilot`
- difficult 策略：`include_difficult`
- 输入尺寸：`384`
- 计划轮数：`30`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\p_cls_yolo_cls_384_include_difficult\weights\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.8529 | 0.6905 | 0.7632 | 0.2000 | 29/13/52/5 | 0.8715 | 0.7495 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "p_cls_yolo_cls_384_include_difficult",
  "kind": "classifier",
  "family": "yolo_cls",
  "imgsz": 384,
  "difficult_policy": "include_difficult",
  "epochs": 30,
  "stage": "pilot",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\p_cls_yolo_cls_384_include_difficult\\weights\\best.pt",
  "tta": "none",
  "temperature": 4.0,
  "operating_points": {
    "0.1": {
      "threshold": 0.8637815948466755,
      "recall": 0.5588235294117647,
      "precision": 0.76,
      "f1": 0.6440677966101696,
      "fpr": 0.09230769230769231,
      "specificity": 0.9076923076923077,
      "tp": 19,
      "fp": 6,
      "tn": 59,
      "fn": 15
    },
    "0.2": {
      "threshold": 0.8104046000984305,
      "recall": 0.8529411764705882,
      "precision": 0.6904761904761905,
      "f1": 0.7631578947368423,
      "fpr": 0.2,
      "specificity": 0.8,
      "tp": 29,
      "fp": 13,
      "tn": 52,
      "fn": 5
    },
    "0.3": {
      "threshold": 0.8012509148541173,
      "recall": 0.8823529411764706,
      "precision": 0.6382978723404256,
      "f1": 0.7407407407407407,
      "fpr": 0.26153846153846155,
      "specificity": 0.7384615384615385,
      "tp": 30,
      "fp": 17,
      "tn": 48,
      "fn": 4
    },
    "0.5": {
      "threshold": 0.7811696154041575,
      "recall": 0.9411764705882353,
      "precision": 0.6037735849056604,
      "f1": 0.735632183908046,
      "fpr": 0.3230769230769231,
      "specificity": 0.676923076923077,
      "tp": 32,
      "fp": 21,
      "tn": 44,
      "fn": 2
    }
  },
  "primary": {
    "threshold": 0.8104046000984305,
    "recall": 0.8529411764705882,
    "precision": 0.6904761904761905,
    "f1": 0.7631578947368423,
    "fpr": 0.2,
    "specificity": 0.8,
    "tp": 29,
    "fp": 13,
    "tn": 52,
    "fn": 5
  },
  "auroc": 0.8714932126696833,
  "auprc": 0.7494558826058973,
  "groups": {
    "bottom": {
      "images": 11,
      "recall": 0.8181818181818182
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
      "recall": 0.6666666666666666
    }
  }
}
```
