# p_cls_resnet18_512_include_difficult

- 状态：`完成`
- 类型：`classifier`
- 阶段：`pilot`
- difficult 策略：`include_difficult`
- 输入尺寸：`512`
- 计划轮数：`30`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\p_cls_resnet18_512_include_difficult\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.9706 | 0.7174 | 0.8250 | 0.2000 | 33/13/52/1 | 0.9362 | 0.8825 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "p_cls_resnet18_512_include_difficult",
  "kind": "classifier",
  "family": "resnet18",
  "imgsz": 512,
  "difficult_policy": "include_difficult",
  "epochs": 30,
  "stage": "pilot",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\p_cls_resnet18_512_include_difficult\\best.pt",
  "tta": "none",
  "temperature": 1.25,
  "operating_points": {
    "0.1": {
      "threshold": 0.6597826490952698,
      "recall": 0.7647058823529411,
      "precision": 0.8125,
      "f1": 0.787878787878788,
      "fpr": 0.09230769230769231,
      "specificity": 0.9076923076923077,
      "tp": 26,
      "fp": 6,
      "tn": 59,
      "fn": 8
    },
    "0.2": {
      "threshold": 0.6013464322081012,
      "recall": 0.9705882352941176,
      "precision": 0.717391304347826,
      "f1": 0.825,
      "fpr": 0.2,
      "specificity": 0.8,
      "tp": 33,
      "fp": 13,
      "tn": 52,
      "fn": 1
    },
    "0.3": {
      "threshold": 0.6013464322081012,
      "recall": 0.9705882352941176,
      "precision": 0.717391304347826,
      "f1": 0.825,
      "fpr": 0.2,
      "specificity": 0.8,
      "tp": 33,
      "fp": 13,
      "tn": 52,
      "fn": 1
    },
    "0.5": {
      "threshold": 0.5894909913310294,
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
    "threshold": 0.6013464322081012,
    "recall": 0.9705882352941176,
    "precision": 0.717391304347826,
    "f1": 0.825,
    "fpr": 0.2,
    "specificity": 0.8,
    "tp": 33,
    "fp": 13,
    "tn": 52,
    "fn": 1
  },
  "auroc": 0.9361990950226244,
  "auprc": 0.8824865802848908,
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
      "recall": 1.0
    }
  }
}
```
