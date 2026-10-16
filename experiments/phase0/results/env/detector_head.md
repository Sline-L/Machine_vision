# Scratch V5 检测头（阶段 0，2026-10-16 核实）

环境：PC `yolo_pro`，Ultralytics **8.4.9**（vendored + pip 一致）；权重 `model/model2/detector.pt`（**YOLO26-p2** 摘要，导出日志 2.5M params）。

## 1. PyTorch / 现网 predict（R0prod、P3 r0c det）

| 项 | 值 |
| --- | --- |
| `getattr(model, "end2end", False)` | **false** |
| 末层类型 | **`Detect`**（非 RT-DETR / 非 end2end 一键 NMS 头） |
| 类别 | 单类 `scratch` |
| 现网分支 | `ScratchV5Runtime.predict` → `YOLO.predict(crop, imgsz=960, conf=0.001, iou=0.7)` → **`result.boxes.conf` 的全局 max**（NMS 后）；再 `apply_temperature` |
| P3 张量路径 | 对已 letterbox 的 RGB **uint8 BCHW** 还原 HWC 后同样 `predict`，与上式一致（手册：NMS 不改变全局 max 的推断，待核；阶段 0 主机端对 PC 参照仍用此路径） |

原始 probe JSON：`results/env/detector_probe.json`（不含图像，仅结构）。

## 2. ONNX 导出（P4）

| 项 | 值 |
| --- | --- |
| 路径 | `experiments/phase0/engines/onnx/detector.onnx`（**勿**在 `model/` 留副本） |
| 参数 | opset **17**，`nms=False`，`dynamic=False`，`imgsz=960`，`batch=1` |
| 输入 | 名 **`images`**，形状 **`[1, 3, 960, 960]`**，float32，**0–1**（与 det960 张量 `/255` 一致） |
| 输出 | 名 **`output0`**，形状 **`[1, 5, 76500]`** |
| 含义（待核，按 Ultralytics detect+NMS-off 惯例） | 5 通道 = **4 框回归 + 1 类分数**；76500 为 anchor 数；**主机端 max 候选置信度** = 对 **第 5 通道（index 4）** 在最后一维取 **max**（见 `p4_o0_detector_ort.py`） |

## 3. O0 检测器 ONNX Runtime 对 r0c（决策要求）

- 脚本：`experiments/phase0/pc/p4_o0_detector_ort.py`
- 结果：`results/pc/p4_o0_detector_summary.json`
- **2026-10-16**：max \|O0_ORT − r0c\|_det ≈ **0.552**（**> 1e-3**）→ **导出问题**，已 **BLOCKED**，**未改**导出参数；须写入 G1 / PC 报告，Jetson TensorRT 检测器仍按手册 **J4 最后** 构建。
- 可能原因（待核）：ONNX 输出布局/激活与 `predict` 后处理不一致，或需与 Ultralytics 导出文档对齐后再定解析式（不在阶段 0 擅自改 export  flags）。

## 4. Jetson J5 检测器（暂缓）

在 PC 本文件与 O0 结论稳定前，**不做检测器 J5**。分类器 J5 按 `logit_raw`；检测器引擎就绪后，从 **原始输出张量** 按本节 ONNX 形状 + 板上实测对齐 `det_max_conf` / `det_n_cand`（≥0.001 计数）。
