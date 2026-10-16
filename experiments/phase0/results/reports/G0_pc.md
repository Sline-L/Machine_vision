# 情报单 G0（PC 部分）

时间: 2026-10-16T19:00+08:00 / 执行者: Composer / 分支: `claude/jetson-defect-detection-cascade-dbbf33` / worktree: `G:\CODE\Machine_vision-phase0`

状态: **OK**

已完成步骤:
- P0：数据集 `G:\CODE\gp-dataset\dataset_defects/scratch_v5`；150/128/236；SHA256 全过；`results/pc/manifest_images.csv`、`calib_manifest.csv`
- P1：`yolo_pro` 环境；`results/env/pc_env.json`；R0prod **150/150** 判定一致，max |Δfused| **5.08e-4**（≤1e-3）
- P2：`experiments/phase0/data/tensors/` **1028** 文件 + `tensor_manifest.csv`（514 stems）
- P3：`results/pc/scores_long.csv` **4626** 行（r0/r0t/r0c）；`pc_noise_baseline` 见 `p3_summary.json`
- P4：ONNX 在 `experiments/phase0/engines/onnx/`；O0 分类器 vs r0c max logit diff **1.30e-4**（≤1e-3）；`onnx_manifest.json`
- P5：本情报单；传输清单见下

未完成与原因:
- 无

关键事实:
- Conda: `D:\ANACONDA\ANACONDA\envs\yolo_pro`；GPU **RTX 4060 Laptop**；驱动 **591.86**
- torch **2.5.1** / torchvision **0.20.1** / ultralytics **8.4.9**（`pc_env.json`）
- 噪声基线（logit |Δ|）：r0c vs r0 max **1.38e-5**；r0t vs r0 max **1.21e-2**、q99 **7.35e-3**（TF32 预期量级，待决策者是否记入 G1）
- 检测器 O0 ORT：`p4_o0_detector_ort.py` 已写入 `scores_long.csv`（cfg=o0, model=det）；vs r0c **max diff ≈ 0.552（BLOCKED，>1e-3）**，见 `p4_o0_detector_summary.json` 与 `detector_head.md`，未改导出参数
- `detector_head.md` 已补交（Detect 头、ONNX I/O 形状）；`model/model2/detector.onnx` 副本已删
- `results/env/pc_env_srtp_yolo.json` + `r0prod_srtp_yolo_boundary.json`（val_069 边界 149/150）
- 传输至 NX：`data/tensors/` ≈ **2.17 GiB**；`engines/onnx/` 三文件 SHA256 见 `onnx_manifest.json`

验收结果:
- P0: 通过
- P1: 通过（150/150，5.08e-4）
- P2: 通过（1028 文件，重复哈希 0 不一致）
- P3: 通过（4626 行，无 NaN）
- P4: 通过（1.30e-4）
- P5: 通过

异常与意外:
- `srtp_yolo` 环境 R0prod **149/150**（`val_069` 阈值边界）；正式 PC 环境定为 **yolo_pro**
- Ultralytics 导出在 `model/model2/detector.onnx` 留副本，已复制到 `engines/onnx/detector.onnx`

请决策者回答的问题:
1. r0t vs r0 的 TF32 噪声（max 1.2e-2）是否作为 G1 报告必报项？
2. O0 检测器是否必须在 PC 侧补全 ONNXRuntime 路径后再冻结，还是允许 Jetson 侧仅用 TensorRT？
3. G0 放行后是否立即启动 J3 INT8 冒烟 + P1 优先级 J4？
