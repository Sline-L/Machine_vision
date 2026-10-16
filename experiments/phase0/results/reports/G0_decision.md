# G0 决定（决策者，2026-10-16）

状态：部分放行。

## 放行
- J3（INT8 冒烟测试）：现在可以做。它不依赖 PC 侧数值。
- 分析侧 A1 到 A6：可以用合成数据写脚本并测试。真实数据先不要读，等 PC 侧 G0 过关。

## 暂缓
- J4 起：等我读到 `G0_pc.md`，确认 P1（R0prod 复现 `val_predictions.csv`，判定 150/150 一致）通过后再放行。原因：INT8 校准缓存由 calib 张量生成，张量若有预处理问题，缓存要重做。

## 对三个问题的回答
1. 风扇。分数与风扇无关，但 TensorRT 构建时 tactic 选择靠实测计时，温度和时钟漂移会让 J7 的重建差异混进热噪声。所以进入 J4 之前把风扇拉满（需要 sudo，由用户执行，命令以板上 `jetson_clocks --help` 为准，待核），之后整个实验保持不变。拉满后在 `j2_power.json` 补一条记录。J8 时延开始前再记一次。pwm=127 若要保留，也必须在所有构建和时延里一致，但我不推荐。
2. workspace 用 4 GB，所有构建保持相同。记录实际值。Orin NX 内存与 CPU 共用，检测器若因 4 GB 构建失败，如实记录一行，不要自行加大。
3. 分析侧合成数据脚本：可以启动，见上。

## 其他
- `gearpro.service` 和 `edgemedic.service` 已停并取消自启。实验全部结束后，需要恢复，请在 G2 里列出恢复命令，由用户决定何时执行。
- Jetson 的 PyTorch 是 2.5.0a0 (nv24.8)，PC 是 2.14。R1 对 R0 的差异里会含 PyTorch 版本差异，A3 归因时要写明。
- 本文件和 `G0_jetson.md` 请 Composer 提交到本分支（`git add` 指定文件，pull --rebase 后推送）。`G0_pc.md` 同样需要推送。

---

# G0 最终决定（读完 G0_pc.md 之后）

状态：全部放行。J3 与 P1 优先级的 J4 到 J8 可以开始。

## 回答 G0_pc 的三个问题
1. r0t 对 r0 的 TF32 噪声（logit 最大 1.21e-2）必报，写进 G1 和最终 summary。它是 A3 归因链里"TF32 本身"一环，也是解释 R0prod 复现差 5.08e-4 的依据。
2. O0 检测器不阻塞 Jetson 侧。分类器的 J3、J4、J5 马上做。检测器引擎（det 的 E1b、E2）在 J4 里放在最后构建。PC 侧并行补一项检查：用 ONNX Runtime CPU 在 det960 张量上跑 `detector.onnx`，取最大候选置信度，与 r0c 的 det_max_conf 比较，结果追加到 `scores_long.csv`（cfg=o0, model=det）。若最大差超过 1e-3，写进 G1 作为导出问题，不要自行改导出参数。
3. 是，立即启动。

## 对 Jetson 侧的补充
- 进入 J4 前风扇拉满，见上一版决定。
- workspace 4 GB。

## 需要补交或确认
- `results/env/detector_head.md`（手册决策 4 要求核实检测头类型和 predict 用的分支）。G0_pc.md 没有提到它。没有它，J5 无法确定从原始输出取最大置信度的方式。请补交，并在 G1 之前写清检测器 ONNX 输出的张量形状与含义。
- G0_pc.md 说 Ultralytics 导出在 `model/model2/detector.onnx` 留下了副本。`model/` 目录不允许改动。请确认该文件未被 git 跟踪（`git status` 应当看不到，因为 `*.onnx` 被忽略），并在实验结束前删除这个副本，只保留 `engines/onnx/detector.onnx`。
- 三个情报单（G0_pc.md、G0_jetson.md、G0.md）请提交到分支 `experiments/phase0/results/reports/`。目前远端分支上只有我写的文件。提交前 `git pull --rebase`。

## 我的观察（供 G1 与分析侧参考，不是指令）
- `srtp_yolo` 环境下 R0prod 为 149/150，val_069 在阈值边界翻转。这是软件环境不同就能翻一张的实例。分析侧在 A5 的近翻转分析里要单独标出 val_069，并把"两个 PC 环境的差异"作为一条额外的噪声基线（需要 PC 侧给出 srtp_yolo 的版本记录，写进 `results/env/`）。
- PC 的 torch 为 2.5.1，Jetson 为 2.5.0a0 (nv24.8)。两者主版本相同，A3 里 R1 对 R0 的差异仍写明版本不同，但不必担心跨大版本。
