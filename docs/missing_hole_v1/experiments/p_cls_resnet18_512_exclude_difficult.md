# p_cls_resnet18_512_exclude_difficult

- 状态：`完成`
- 类型：`classifier`
- 阶段：`pilot`
- difficult 策略：`exclude_difficult`
- 输入尺寸：`512`
- 计划轮数：`30`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\p_cls_resnet18_512_exclude_difficult\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.9118 | 0.7949 | 0.8493 | 0.1231 | 31/8/57/3 | 0.9493 | 0.9091 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "p_cls_resnet18_512_exclude_difficult",
  "kind": "classifier",
  "family": "resnet18",
  "imgsz": 512,
  "difficult_policy": "exclude_difficult",
  "epochs": 30,
  "stage": "pilot",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\p_cls_resnet18_512_exclude_difficult\\best.pt",
  "tta": "none",
  "temperature": 1.075,
  "operating_points": {
    "0.1": {
      "threshold": 0.7564566083101195,
      "recall": 0.8529411764705882,
      "precision": 0.8529411764705882,
      "f1": 0.8529411764705882,
      "fpr": 0.07692307692307693,
      "specificity": 0.9230769230769231,
      "tp": 29,
      "fp": 5,
      "tn": 60,
      "fn": 5
    },
    "0.2": {
      "threshold": 0.6650234587030996,
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
      "threshold": 0.5700829593825261,
      "recall": 0.9411764705882353,
      "precision": 0.6956521739130435,
      "f1": 0.7999999999999999,
      "fpr": 0.2153846153846154,
      "specificity": 0.7846153846153846,
      "tp": 32,
      "fp": 14,
      "tn": 51,
      "fn": 2
    },
    "0.5": {
      "threshold": 0.27052438064172585,
      "recall": 1.0,
      "precision": 0.5483870967741935,
      "f1": 0.7083333333333333,
      "fpr": 0.4307692307692308,
      "specificity": 0.5692307692307692,
      "tp": 34,
      "fp": 28,
      "tn": 37,
      "fn": 0
    }
  },
  "primary": {
    "threshold": 0.6650234587030996,
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
  "auroc": 0.9493212669683257,
  "auprc": 0.9091411624252188,
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
      "recall": 1.0
    }
  }
}
```
