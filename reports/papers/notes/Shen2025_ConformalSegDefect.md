# Shen & Liu 2025 工业表面缺陷共形分割（Mask R-CNN + CRC）
- 完整引用：Cheng Shen, Yuewei Liu（兰州大学）. Conformal Segmentation in Industrial Surface Defect Detection with Statistical Guarantees. arXiv:2504.17721v1 [cs.LG], 24 Apr 2025，页眉"Under Review"。他文（Yan & Sun 2026 参考文献[28]）引用为：Mathematics 13(15):2430 (2025), doi:10.3390/math13152430（PDF本身未写，间接来源）。
- 来源核实：本地 OA_arXiv/2504.17721.pdf，13页；首页 v1，24 Apr 2025。与已知元数据的差异：本地是预印 v1，期刊版（MDPI Mathematics）内容可能与 v1 不同，引用时应以期刊版为准，需另行核对。
- 阅读深度：全文（13页，含表1-3、图3-5、参考文献）。图4用栅格化核对了第10页。
- 一句话：对 Mask R-CNN 的像素概率图用 CRC 选阈值，使"像素级 FDR/FNR 的期望"不超过 α，在 Severstal 和 NEU-DET 上测六种骨干。
- 问题设定：图像 x_i，像素概率图 f(x)∈[0,1]^{h×w}；预测集 C_i(λ)={(j,k): f≥1-λ}（式4）；校准集与测试集 i.i.d./可交换。风险是逐图像像素比例：FDR 损失 ℓ_i = |C_i \ y_i| / (|C_i|∨1)（式5，用 ε 避免空集除零），FNR 损失 = 未覆盖缺陷像素 / |y_i|（式13）。
- 方法：按 CRC 求 λ̂=inf{λ: n/(n+1)·L_n(λ)+1/(n+1) ≤ α}（式8）；推理时对测试概率图取 ≥1-λ̂ 的像素。单参数 λ，单阈值。
- 保证 / 结论：E[ℓ_{n+1}(λ̂)] ≤ α（式9），期望/边际保证，对校准集和测试点联合平均；无 δ；单阈值；无级联、无部署。
- 实验：Severstal（文称25,894张，2560×1600，4类）、NEU-DET（1800张，200×200，6类）；骨干 ResNet-50/34、SqueezeNet、ShuffleNetv2_x2、MobileNetv3-Large、GhostNetv3（表1）。表2基线性能很低：Severstal 上 ResNet-50 IoU 0.1963/Precision 0.3478/Recall 0.2500；NEU 上 ResNet-50 IoU 0.3570。FDR 控制图3：α∈[0.1,0.9]，经验FDR在参考线以下；Severstal 上 ResNet-50 在 α=0.7 时 FDR 0.677。FNR 图4。消融表3：NEU-DET，ResNet-50-FPN，划分比例 0.3/0.5/0.7，α=0.1 时经验FNR 0.0911/0.0857/0.0817，α=0.2 时 0.1929/0.1357/0.1813，α=0.3 时 0.2834/0.2754/0.2707（三折验证）。
- 局限：作者承认：未来要做多缺陷类别、动态校准应对分布漂移（结论）。我看出的：
  (1) FNR 对无缺陷图未定义：式13分母是真值缺陷像素数 |y_i|，无缺陷图为0；原文没有定义这类图的损失，也没说是否只在有缺陷图上校准（原文未见）。对我们的"零件级漏检"定义有直接警示：必须明确只在有缺陷零件上算漏检，或把无缺陷零件损失定为0并说明稀释效应。
  (2) 图4显示：目标 α≥0.4 后经验 FNR 在约0.3处平台，不再随目标上升（栅格化第10页所见），说明高 α 区的"保证"是平凡的（不是紧的）；文字（第4.4.2节）写"α从0.1增至0.9，ResNet-50 在NEU上FNR从0.436降到0.305"，与"目标α=0.1时FNR≤0.1"以及表3的0.0857不一致；很可能该句指的是别的量（符号在抽取中丢失），我无法确定，标为疑点。
  (3) 表2基线很弱（Severstal 召回0.25），FDR 目标 0.7-0.9 才有意义，实用性存疑。
  (4) 图5中预测集大小在低 α 为0，原因原文未解释。
  (5) 引言中的数字（"ASTM 62%""human FDR 18.7%""94% detection accuracy"）仅引用二手文献[1][2]，且作者把 FDR 同时写成 False Detection Rate 与 False Discovery Rate；Severstal 各类占比加起来恰为100%，与"一图可含多类"并存，数据说明不够清楚。（我的判断）可信度偏低，不宜作为强证据引用。
- 和我们的关系：需区别 + 反面提醒。同领域（Severstal 是我们数据集之一），风险是像素级期望，单阈值，无级联，无部署；证明我们在Severstal上的"部件级、概率1-δ、两阈值"是不同问题。对声明(a)：不满足"部件级高概率保证""级联""部署验证"。
- 可引用的句子："the expected FDR of the resulting prediction set on unseen test data is rigorously controlled to be no greater than the predefined risk level"（第3.3节）；校准集占比0.3到0.7均满足FNR约束（表3）。
- 疑点：期刊版（Mathematics 13(15):2430）与v1差异未核；第4.4.2节数字与表3不一致；无缺陷图的FNR定义原文未见；第4.5节 Pearson r=0.91 等数据的统计依据原文未详。
