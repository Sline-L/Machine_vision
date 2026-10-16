# G1 补交后的决定（决策者，2026-10-16）

## DLA（更正此前判断）
- 环境正常。严格构建失败的原因是 GlobalAveragePool 属 REDUCE 类，DLA 不支持（c1、c2 都有）。严格 DLA 构建对这两个模型不可能成功，这是可部署性结果。
- 回退构建是真实 DLA+GPU 引擎：c2 约 47 层在 DLA，c1 约 221 层在 DLA。build_log 里 dla=0 是解析错误。
- 命名：DLA+GPU(n_gpu/n_total)。关键数据：DLA/GPU 切换次数（子图数）。
- DLA 分配以 trtexec verbose 列表为准，inspector JSON 交叉核对。

## INT8
- v1：Pearson 0.963 到 0.995，AUROC 基本不变，判为整体偏移，非校准 bug。放行 e3、E4 v2。
- AUROC 不变不等于阈值附近判定不变。A2 必须按缺陷/正常分层、带符号看 Δ。

## 检测器分数：选 (A) 与 predict 等价
- 现网判定用 predict 的分数，检测器占融合权重 0.75。
- 十图中 predict 在部分 stem 高于 raw/ORT，NMS 不能使最大置信度升高，故不是 NMS 差异。
- 假设（待核）：检测器为 end2end 头，predict 走 one2one，ONNX [1,5,76500] 是 one2many 稠密输出。
- 另需排除：张量为 RGB，predict 将 numpy 输入当 BGR，可能通道颠倒。
- PC 侧按 1 到 6 步诊断；授权导出 detector_e2e.onnx（不覆盖原文件），ORT 对 predict 最大置信度差 ≤1e-3。
- 通道颠倒若成立，所有已有 det 分数需重算，先报告再决定。

## 风扇与时钟
- 自动温控会把 pwm 拉回，不再强改；记录温度与实际 pwm，降频数据作废重测。
- 板钟 +17 天，已知。

## 放行
- Jetson v2：e1b,e1a,e2,e3,e4,e5,e6（串行，单进程锁），R1，J5/J7/J8（分类器）。
- 暂停：检测器、E7、fixed timing cache。
- 分析侧：仍只用合成数据，等 G1b。
