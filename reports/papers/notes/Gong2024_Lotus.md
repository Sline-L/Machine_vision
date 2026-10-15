# Gong 2024 Lotus: 两阶段检测器的在线热与延迟波动管理
- 完整引用：Yifan Gong, Yushu Wu, Zheng Zhan, Pu Zhao, Liangkai Liu, Chao Wu, Xulong Tang, Yanzhi Wang，"Lotus: learning-based online thermal and latency variation management for two-stage detectors on edge devices"，DAC '24（第 61 届 Design Automation Conference），June 23-27, 2024, San Francisco；ACM ISBN 979-8-4007-0601-1/24/06；DOI 10.1145/3649329.3657310；arXiv:2410.10847v1 [cs.CV]，1 Oct 2024，7 页。
- 来源核实：本地 OA_arXiv/2410.10847.pdf；首页 v1，1 Oct 2024；DAC'24 信息取自首页版权块；与已知元数据一致。
- 阅读深度：全文（7 页）。
- 一句话：用深度强化学习（DQN）在每帧推理里两次（开始与 RPN 之后）联合调 CPU/GPU 频率，降低 Faster/Mask R-CNN 在 Jetson Orin Nano 和小米 Mi 11 Lite 上的延迟波动和温度。
- 问题设定：**"two-stage detector"指 R-CNN 类（区域建议+分类）两阶段检测器，不是"分类器放行+检测器复检"的级联。** 目标：min 平均延迟 + α·方差 + β·违反延迟约束的比例（式 (1)），且 CPU/GPU 温度不超过限。
- 方法：状态含阶段、CPU/GPU 温度、频率档、剩余时间，第二次决策多一个建议框数量；奖励为延迟项 tanh 与波动项 1/(1+σ) 加温度项；单个 Q 网络用 0.75× 与 1.0× 两种宽度；两个经验回放缓冲；ε-greedy "cool-down" 动作（过热时以概率 ε 选更低频率）。智能体跑在桌面 2080Ti，经 socket 控制客户端；总开销 8.52 ms/次推理（Q 网络 0.42 ms，传输 1.92 ms/消息）。
- 保证 / 结论：无保证。摘要/引言：速度提升最多 30.8%，波动降低最多 72.8%，满足延迟约束的比例最多提升 43.8%。
- 实验：Orin Nano（6 核 A78AE，1024 核 GPU，8GB）；模型 Faster R-CNN、Mask R-CNN（对照 YOLOv5）；数据 KITTI、VisDrone2019；基线 默认治理器（schedutil、nvhost_podgov）与 zTT。每次 3000 次迭代，室温 25°C。Fig.1：延迟"variation"，KITTI 上 Faster R-CNN/Mask R-CNN/YOLOv5 为 134.10/194.64/2.75 ms，VisDrone 上为 198.85/200.18/10.38 ms（原文称"inference variation"，未明说是标准差）。第二阶段延迟随建议框数增长（Fig.2）；第一阶段约占 80% 延迟，第二阶段贡献主要波动（Faster R-CNN KITTI 第二阶段波动可达 159.5 ms，平均总延迟 441.9 ms）。
  Table 1（Orin Nano，μ/σ ms，满足率）：Faster R-CNN KITTI 默认 434.6/139.8/51.4%，zTT 363.7/85.6/55.5%，Lotus 343.2/68.6/66.5%；VisDrone 默认 686.0/241.1/29.4%，zTT 577.6/167.5/46.3%，Lotus 523.5/102.9/71.1%。Mask R-CNN KITTI 默认 443.9/148.0/59.8%，zTT 408.3/111.7/87.1%，Lotus 388.5/88.9/95.2%；VisDrone 默认 768.4/260.4/39.0%，zTT 584.3/114.2/50.1%，Lotus 531.4/70.7/74.9%。（表头符号丢失，按行顺序与正文数字 30.8%、72.8% 相互验证一致。）
  **热降频对延迟波动的影响（任务要求）**：全文没有给出"热降频开/关"的对照数字，也没有把热降频与建议框数量两个来源拆分出来；Fig.1 的 variation 是数据集层面的，与热状态无关地归因于建议框数量动态（正文与 Fig.2）。关于热降频的陈述是定性的："thermal throttling will be activated to decrease the frequency to a very low level"（相关工作段，针对无风扇手机），未见量化。风扇配置原文未见。
- 局限：作者承认的很少（结论只有一段）。我的看法：（1）只有两款设备；（2）延迟约束随数据集和模型不同设置，且未给出（已读部分）；（3）控制器在桌面 GPU 上，经 socket；（4）没有能耗数字；（5）Mask R-CNN VisDrone 上提升 30.8% 是对默认治理器，且默认治理器设置未必优；（6）与我们的 FP32/TensorRT/DLA 无关。
- 和我们的关系：背景/需区别。可引用的只有一点：Jetson 上运行重检测器（两阶段 R-CNN）时延迟方差由内容（建议框数）和热/频率共同造成，对"检测器调用延迟不是常数"有旁证——这与我们级联里"检测器调用率节省计算量"相关：检测器耗时是输入相关的，平均节省不等于尾部节省。区别：它的"两阶段"是检测器内部结构；它不放行/拒绝零件，没有任何漏检保证。**不构成"已有人做了我们的组合"。**
- 可引用的句子：（可转述）Faster/Mask R-CNN 在 Orin Nano 上的延迟波动远大于 YOLOv5，原因之一是第二阶段计算量随建议框数变化（Fig.1、Fig.2）；两阶段检测器第一阶段约占总延迟 80%（§4.2）。
- 疑点："variation" 的统计定义（Fig.1）未明说；热降频开关的因果证据不足；比例"43.8%"对应哪个设置在已读表中未直接对应（Table 1 中 Mask R-CNN VisDrone 满足率 39.0→74.9% 提升 35.9 个百分点，正文也给 35.9% 与 24.8%；43.8% 在引言，未在表中找到，Mi 11 Lite Table 2 的某项可能）。
