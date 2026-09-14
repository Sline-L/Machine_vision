# Model Artifact Contract

Dataset 仓产出；GearPro 只消费。不要把 `Machine_vision_dataset` git merge 进本仓。

```text
Machine_vision_dataset
        │ produces
        ▼
runtime_bundle/   (manifest + inference_config + weights + SHA256)
        │ consumes
        ▼
GearPro  (load → verify SHA → schema → warmup)
```

Runtime 不知道 `dataset_defects`、`train_scratch_v5.py`、`runs/`。当前冻结包是 Scratch V5，路径 `model/model2/`。Missing Hole 不进入本阶段 runtime。

## 目录

```text
runtime_bundle/
├── manifest.json
├── inference_config.json
├── classifier_1.pt
├── classifier_2.pt
└── detector.pt
```

Schema：`docs/edgemedic/runtime-bundle.schema.json`（`schema_version`: `runtime-bundle.v1`）。

## evaluation 必须拆开

| 块 | 含义 |
| --- | --- |
| `evaluation.validation` | 参与过模型/阈值选择的指标。`blind` 必须为 false（若参与过选择）。 |
| `evaluation.locked_test` | 独立锁定测试。`locked` 必须为 true。不得用于继续训练或调阈值。 |

加载时 `gp.bundle.load_runtime_bundle` 会校验 family、产物文件名、manifest SHA 与 `inference_config` SHA 一致。文件内容哈希仍由 `load_model2_config` 核对。

## 当前交付

`bundle_id`: `scratch-v5-2026-09-14`。验证集 Recall 0.9767 / FPR 0.0841 **不是**盲测。锁定 `test_scratch` Recall 0.8065 / FPR 0.1681。
