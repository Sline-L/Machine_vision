# G1 决定（决策者，2026-10-16）

状态：部分放行。v1 引擎全部作废（归档，不进分析）。

## 原因
- e1b 由两个并行构建进程产生，TensorRT 按实测计时选内核，并行负载污染 tactic 选择，影响 J7 重建差异。
- 12 个 DLA 严格构建失败（无日志）；回退构建 0 层在 DLA（原 build_log 的 n_layers 解析读错字段）。当前没有任何 DLA 引擎。e5/e6 在表里写作"请求 DLA，实际 0 层在 DLA"。
- e3 对 R0 的 logit 差最大 3.95（c1）、2.33（c2），需先排除校准 bug（看相关性、AUROC、校准器输入）。
- 18 行失败 = 12 行 DLA 严格构建 + 6 行 det（det 失败是 detector.onnx 未传到板上）。

## 放行
- 立即：DLA 最小诊断（trtexec verbose）、INT8 排错、v2 串行重建 e1b/e2/E1a（pwm=255）、R1。
- e3、E4：等 INT8 排错结果后放行。
- Jetson 侧 det：暂停，等 PC 修好 O0 det（与 r0c 差 0.552）。

## 暂不做
- fixed timing cache、E7、任何 DLA 分数结论。

## 记录
- 板子时钟比真实日期早约 17 天（日志 ts 需按此理解，分数不受影响）。
- 目前最有价值的信号（待 v2 确认）：e2 c1 三次重建 503/514 张有位差，最大 logit 差 0.145，与 FP16 对 FP32 的 0.106 同量级。
- A4 的 only_c1/only_c2 场景可用 R0 的 det 分数计算融合分数，不依赖 Jetson det；all_same 要等 det 引擎。
