# 检测器通道问题的决定（决策者，2026-10-16）

## 对 PC 第 1 到 3 步的审阅
- 头结构：end2end=False，predict 走 one2many + NMS。此前 one2one 的猜测错误。现有 detector.onnx（one2many 稠密 [1,5,76500]）与 predict 同一分支。
- 步骤 2 的"通道颠倒不成立"判据循环：r0 本身就是把 RGB HWC 数组传给 predict 生成的，Ultralytics 对 numpy 输入默认当 BGR 并翻转，所以 r0 的模型输入实际是红蓝对调的。正确判据是哪个更贴近 r0prod（BGR 传入，现网口径）。
- 旁证：predict(RGB 数组) 对 predict(BGR 数组) 的差 0.0435，几乎等于 predict(RGB 数组) 对 raw forward 的差 0.0436；raw forward 与 ORT 直接吃 RGB 张量，模型看到的是正确通道。推断（未验证）：r0、r0c、r0t 的 det 行通道对调，ORT 与 Jetson 才是正确的。
- 几何（矩形 vs 方形 letterbox）不是主因：val 图近似方形。

## 检测器分数定义（待验证成立后生效）
RGB 张量 /255 送入模型，取输出 ch4 的全局最大值（sigmoid 后，不做 NMS），主机端取最大。低于 0.001 的原值保存，分析侧按现网规则处理。R0 系用 raw forward，不经过 predict。

## 动作
- PC：按指示验证（1a、1b、1c），成立则归档旧 det 行并重算 r0、r0c、r0t、o0 的 det 行；detector_e2e.onnx 废弃。
- Jetson：v2 照常进行；检测器等 PC 通过后再放行。
