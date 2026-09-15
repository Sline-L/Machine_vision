# p_cls_yolo_cls_512_exclude_difficult

- 状态：`完成`
- 类型：`classifier`
- 阶段：`pilot`
- difficult 策略：`exclude_difficult`
- 输入尺寸：`512`
- 计划轮数：`30`
- 权重：`F:\Work\VSCode\Projects\DATASET\runs\missing_hole_v1\p_cls_yolo_cls_512_exclude_difficult\weights\best.pt`

## 验证集主工作点

| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.7353 | 0.6944 | 0.7143 | 0.1692 | 25/11/54/9 | 0.8561 | 0.7785 |

主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。

## 配置

```json
{
  "name": "p_cls_yolo_cls_512_exclude_difficult",
  "kind": "classifier",
  "family": "yolo_cls",
  "imgsz": 512,
  "difficult_policy": "exclude_difficult",
  "epochs": 30,
  "stage": "pilot",
  "seed": 20260913,
  "weights": "F:\\Work\\VSCode\\Projects\\DATASET\\runs\\missing_hole_v1\\p_cls_yolo_cls_512_exclude_difficult\\weights\\best.pt",
  "tta": "flip",
  "temperature": 4.0,
  "operating_points": {
    "0.1": {
      "threshold": 0.8803409539116176,
      "recall": 0.5,
      "precision": 0.7727272727272727,
      "f1": 0.6071428571428571,
      "fpr": 0.07692307692307693,
      "specificity": 0.9230769230769231,
      "tp": 17,
      "fp": 5,
      "tn": 60,
      "fn": 17
    },
    "0.2": {
      "threshold": 0.8474139745056956,
      "recall": 0.7352941176470589,
      "precision": 0.6944444444444444,
      "f1": 0.7142857142857144,
      "fpr": 0.16923076923076924,
      "specificity": 0.8307692307692307,
      "tp": 25,
      "fp": 11,
      "tn": 54,
      "fn": 9
    },
    "0.3": {
      "threshold": 0.8011499696125571,
      "recall": 0.7941176470588235,
      "precision": 0.5869565217391305,
      "f1": 0.675,
      "fpr": 0.2923076923076923,
      "specificity": 0.7076923076923076,
      "tp": 27,
      "fp": 19,
      "tn": 46,
      "fn": 7
    },
    "0.5": {
      "threshold": 0.7349636588656147,
      "recall": 0.9411764705882353,
      "precision": 0.5161290322580645,
      "f1": 0.6666666666666666,
      "fpr": 0.46153846153846156,
      "specificity": 0.5384615384615384,
      "tp": 32,
      "fp": 30,
      "tn": 35,
      "fn": 2
    }
  },
  "primary": {
    "threshold": 0.8474139745056956,
    "recall": 0.7352941176470589,
    "precision": 0.6944444444444444,
    "f1": 0.7142857142857144,
    "fpr": 0.16923076923076924,
    "specificity": 0.8307692307692307,
    "tp": 25,
    "fp": 11,
    "tn": 54,
    "fn": 9
  },
  "auroc": 0.8561085972850678,
  "auprc": 0.7785148081695349,
  "groups": {
    "bottom": {
      "images": 11,
      "recall": 0.8181818181818182
    },
    "oblique": {
      "images": 12,
      "recall": 0.6666666666666666
    },
    "side": {
      "images": 14,
      "recall": 0.7857142857142857
    },
    "difficult": {
      "images": 3,
      "recall": 0.3333333333333333
    }
  }
}
```
