# Jetson 侧与查新：候选文献名单

> 2026-10-15。只是候选名单，供下载。**所有条目都只读到摘要页、Crossref 元数据或检索片段，没有一篇读过全文。**
> 元数据来源：arXiv 摘要页或 API、Crossref、NVIDIA 官方页面。标"待核"的是没打开权威页面的。
> 抓取工具返回的是转述加短引文，不是逐字原文；表中引号内的句子只在注明"原文句"时才是逐字。
> OA = 可免费下载。

---

## A. 功耗测量与功耗模式 / DVFS（动态电压频率调节）

| # | 引用 | ID | OA | 要点（仅据所读摘要或片段） | 状态 |
|---|---|---|---|---|---|
| A1 | Shalavi N, Khoshsirat A, Stellini M, Zanella A, Rossi M. Accurate Calibration of Power Measurements from Internal Power Sensors on NVIDIA Jetson Devices. arXiv v1, 2023-06-19 | arXiv:2306.13107 | OA | 板载传感器有误差，校准后据称在 ±3% 内（来自 PDF 检索片段，摘要未读）。能耗测量方法的核心候选 | 元数据已核；是否有期刊版待核 |
| A2 | Jahanifar H, et al. AgriJetsonBench: External-Power-Referenced TensorRT Benchmarking of Agricultural Vision Models on Jetson Edge Platforms. arXiv, 2026-08-02 | arXiv:2608.00927 | OA | 外接功率计做参照；报 p95 时延和 J/推理；板载读数比外接低约 1.988 W（76,691 个对齐样本）。农业场景，AGX Orin 与 Orin Nano Super，无 NX | 摘要页已核 |
| A3 | Prashanthi S K, et al. Pagoda: An Energy and Time Roofline Study for DNN Workloads on Edge Accelerators. arXiv, 2025-09-24 | arXiv:2509.20189 | OA | AGX Orin 上跨功耗模式；摘要称默认 MAXN 不是最省能耗的模式，按模型选功耗模式最多省 15% 能耗而时延增加很少 | 摘要页已核；非 NX |
| A4 | Arya M, Simmhan Y. Understanding the Performance and Power of LLM Inferencing on Edge Accelerators. arXiv v2（首次提交 2025-06-11） | arXiv:2506.09554 | OA | Orin AGX 上改批大小、序列长度、量化，并探索自定义功耗模式 | 元数据已核，摘要未读 |
| A5 | Kang J. Edge-Inference Governors Need Memory-Clock State. arXiv v1 2026-06-15，v3 2026-07-08 | arXiv:2606.16106 | OA | 逐字摘要已读（API）。主结果是内存时钟（EMC）：不看 EMC 的 GPU 拟合在紧截止时间下漏掉 25–28% 周期，加入 EMC 后 ≤0.9%。**摘要中未见"小模型满频与最低频能耗几乎相同"这一论断**，可能在正文，待读 | 摘要已核；v1 标题可能不同（待核）；单人预印本 |
| A6 | Chen J, et al. DVFS for Small Language Model Inference on Mobile Edge Devices | arXiv:2609.13153 | OA | 片段：联合调 GPU 与 EMC 频率以最小化每 token 能耗，与 A5 方向一致 | 元数据已核；**编号 2609 与标注日期 2026-07-08 不符，待核** |
| A7 | Park J-G, et al. Energy-Efficient GPU DVFS for Fine-Tuning of SLMs on Resource-constrained Embedded Devices. arXiv, 2026-07-07 | arXiv:2607.05933 | OA | 片段：AGX Orin 上相对 MAXN 平均省 13.11%（最多 26.73%）。是微调不是推理 | 摘要未读 |
| A8 | Han Y, et al. DVFS-Aware DNN Inference on GPUs: Latency Modeling and Performance Analysis | arXiv:2502.06295 | OA | 片段：DVFS 感知时延模型。平台是否 Jetson 未确认 | 待核 |
| A9 | Electronics 15(11): 2451 (2026)，题名为 Benchmarking Large Language Model Inference on Limited-Resource Edge Systems | mdpi.com/2079-9292/15/11/2451 | OA | 片段：Jetson Orin Nano Super，用外接功率计测能耗 | **作者、DOI 未取到，待核** |
| A10 | NVIDIA. Jetson Linux Developer Guide r36.4, Platform Power and Performance（Orin Nano/NX/AGX 系列） | docs.nvidia.com/jetson/archives/r36.4/... | OA | nvpmodel 与热管理的官方依据 | 见 D1；功耗模式章节本轮未读 |

**缺口**：tegrastats、jtop、INA3221 内核文档均未抓到；sysfs 采样率、外接分流器验证（A1、A9 之外）未覆盖。

## B. GPU 与 DLA（深度学习加速器）

| # | 引用 | ID | OA | 要点 | 状态 |
|---|---|---|---|---|---|
| B1 | Raju V. Achieving Near-Zero-Overhead Multi-Model Hierarchical Classification in Real-Time Detection Pipelines. arXiv, 2026-08-12 | arXiv:2608.11770 | OA | Orin NX：DLA 上 INT8 分类（无 GPU 回退）+ GPU 检测器；1080p 下 12.5 FPS，单独检测器 13.3 FPS。准确率 75%→94.0% | **两路核查对"94% 来自什么做法"表述不一致**：一说是手动动态范围，一说含 QAT。要读正文确认，不要在论文里写 QAT |
| B2 | Dagli I, Belviranli M. Shared Memory-contention-aware Concurrent DNN Execution for Diversely Heterogeneous SoCs (HaX-CoNN). PPoPP 2024. | arXiv:2308.05869；doi:10.1145/3627535.3638502 | arXiv 版 OA | Orin、Xavier、骁龙 865；摘要称内存争用最多降 45%，延迟最多改善 32%。摘要未出现 DLA 与能耗 | 摘要页已核；页码待核 |
| B3 | Tayal M, Simmhan Y. Evaluating Multi-Instance DNN Inferencing on Multiple Accelerators of an Edge Device. arXiv, 2025-03-12 | arXiv:2503.09546 | OA | 多个 ResNet50 实例：CUDA 核加 Tensor 核有收益，加入 DLA 因争用而变差。设备为 Orin AGX 仅来自检索结果 | 摘要页已核；5 页预印本 |
| B4 | Majeed A A, Meribout M, Sali S M. Scheduling Techniques of AI Models on Modern Heterogeneous Edge GPU – A Critical Review. arXiv v1 2025-06-02，v2 2026-07-12 | arXiv:2506.01377 | OA | Jetson 多加速器调度综述 | 摘要页已核；**引用须写版本；是否已正式发表待核** |
| B5 | Mittal S. A survey on optimized implementation of deep learning models on the NVIDIA Jetson platform. J Syst Archit, 2019 | — | 学校 | — | **元数据未核（检索被拒）** |
| B6 | NVIDIA. TensorRT 文档 Working with DLA | docs.nvidia.com/deeplearning/tensorrt/latest/inference-library/work-with-dla.html | OA | 页面称：DLA 从 TensorRT 11.4.0 起支持，平台为 Windows on ARM（beta）；11.4.0 不支持 JetPack；11.0–11.3 不可用，要用 DLA 应 "remain on TensorRT 10.7" | 已打开（转述加短引文），**需你核原页** |

**本项目设备信息（用户提供，未经官方页面核对）**：DLA 用 TensorRT 10.7；板子内存 16 GB DDR。TensorRT 10.7 与 B6 页面里 "remain on TensorRT 10.7" 一致。D4（Molleda）的 INT8 分割引擎失败发生在 TensorRT 10.3，不能直接推到 10.7，要在我们的板子上自己试。JetPack 版本、Orin NX 的 DLA 核数仍待核。

**GPU 与 DLA 的性能功耗比：本轮 0 条直接证据。** 建议你在 Google Scholar 里自己搜 "Jetson DLA energy / power / performance per watt"。
**DLA 的 INT8 精度问题**：目前只有 B1。
**官方文档待核项**：Orin NX 是否有 2 个 DLA 核；DLA 的 INT8 层支持矩阵；TensorRT 10.16.1 发行说明里一句 "Orin DLA is not supported at this time"（只见搜索摘要，与 B6 有潜在冲突）；JetPack 实际自带的 TensorRT 版本。

## C. TensorRT 量化、校准与引擎重建

| # | 引用 | ID | OA | 要点 | 状态 |
|---|---|---|---|---|---|
| C1 | Wu H, Judd P, Zhang X, Isaev M, Micikevicius P. Integer Quantization for Deep Learning Inference: Principles and Empirical Evaluation. arXiv, 2020-04-20 | arXiv:2004.09602 | OA | 量化参数（校准）选择的原理与实证；称 8-bit 流程在所研究网络上精度保持在浮点基线 1% 内 | 摘要页已核；max/entropy/percentile 具体章节待读 |
| C2 | Nagel M, et al. A White Paper on Neural Network Quantization. arXiv, 2021-06-15 | arXiv:2106.08295 | OA | PTQ（训练后量化）/QAT（量化感知训练）综述与流程 | 只核元数据 |
| C3 | Xia G, Ha S, Azevedo T, Maji P. An Underexplored Dilemma between Confidence and Calibration in Quantized Neural Networks. NeurIPS 2021 ICBINB 研讨会。arXiv v1 2021-11-10，v2 2021-12-02 | arXiv:2111.08163 | OA | 低置信预测在 PTQ 后更易翻转，高置信更稳。CIFAR-100、ImageNet 上多个 CNN | 摘要页已核（转述） |
| C4 | Kuang J, Wong A. On Calibration of Modern Quantized Efficient Neural Networks. ICCV 2023 Workshop 扩展摘要 | arXiv:2309.13866 | OA | 位宽越低校准越差（4-bit 激活尤甚）；温度缩放可降 ECE（校准误差） | 摘要页已核；篇幅很短 |
| C5 | Hooker S, Courville A, Clark G, Dauphin Y, Frome A. What Do Compressed Deep Neural Networks Forget? arXiv v1 2019-11-13，v3 2021-09-06 | arXiv:1911.05248 | OA | 压缩后总体精度几乎不变，但对长尾样本影响不成比例 | 摘要页已核；**刊物页未写，不要自行补** |
| C6 | Karimov T, Imani H, Kazakov A. Quantization Robustness to Input Degradations for Object Detection. arXiv, 2025-08-27，v3 2026-05-01 | arXiv:2508.19600 | OA | YOLO 在 TensorRT 静态 INT8：提速约 1.5–3.3 倍，干净数据 mAP50-95 降约 3–7%；混合校准集总体未优于标准校准集 | 摘要页已核；**设备是否 Jetson 待核** |
| C7 | Dimitrovski I, et al. Towards Practical Precision Agriculture: Real-Time Fruit Detection and Video Analytics on Embedded Edge Hardware. arXiv, 2026-09-11 | arXiv:2609.13551 | OA | Orin Nano Super 上 YOLO26s：TensorRT FP16 相对 PyTorch FP32 mAP@50:95 仅降 0.0020–0.0054，能耗降约 64–66%（后两项来自检索片段） | 摘要页已核；只报 mAP |
| C8 | NVIDIA. TensorRT 文档 Precision Control（含算法选择与可重复构建） | docs.nvidia.com/deeplearning/tensorrt/latest/inference-library/precision-control.html | OA | 原文句："different invocations of the builder will typically not result in engines that return bit-identical results"；"system noise can determine which one is chosen on any particular run of the builder"；可用可编辑计时缓存（kEDITABLE_TIMING_CACHE）固定各层 tactic | **需补 TensorRT 版本号和访问日期** |
| C9 | NVIDIA. TensorRT 10.x Troubleshooting（FAQ） | docs.nvidia.com/deeplearning/tensorrt/10.x.x/reference/troubleshooting.html | OA | 校准表不保证跨 TensorRT 版本兼容，换版本应重新生成；引擎跨设备/版本默认不可用 | 已核；有一处为转述，写作前逐字复核 |
| C10 | Migacz S. 8-bit Inference with TensorRT. NVIDIA GTC 2017, S7310 | — | 待核 | 熵（KL）校准出处 | **未打开，链接可能失效** |
| C11 | NVIDIA. Polygraphy README | github.com/NVIDIA/TensorRT/tree/main/tools/Polygraphy | OA | 可跨后端比较结果、隔离出问题的 tactic | 只核 README；精度调试专页链接 404 |

**不能当官方证据**：NVIDIA 论坛对 TensorRT 8.6 指南的二手转引（"校准缓存在融合前校准则可跨设备"）。设备方向的可移植性官方原文待核。
**缺口**：没找到直接测 PyTorch FP32 对 TensorRT FP16/INT8 的**逐样本分数漂移或判定翻转率**的论文，找到的只报 mAP；也没找到直接测 TensorRT 校准器对 ECE 影响的文献。

## D. 热降频与工业部署

| # | 引用 | ID | OA | 要点 | 状态 |
|---|---|---|---|---|---|
| D1 | NVIDIA. Jetson Linux Developer Guide r36.4, Thermal Management > Thermal Specifications | docs.nvidia.com/jetson/archives/r36.4/DeveloperGuide/SD/PlatformPowerAndPerformance/JetsonOrinNanoSeriesJetsonOrinNxSeriesAndJetsonAgxOrinSeries.html | OA | 软件降频 99.0 °C，硬件降频 103.0 °C，软件关机 104.5 °C，硬件关机 105.0 °C；硬件降频时钟限制三档 87.5/75/50% | **°C 为抓取工具换算，页面末尾约 24k 字符未读，请你核原页** |
| D2 | Krišlauks R, et al. Ambient Temperature Impact on the Thermal Behavior and Power Consumption of the NVIDIA Jetson AGX Orin in an Outdoor Enclosure. Electronics 15(11): 2467 (2026) | doi:10.3390/electronics15112467 | OA (CC BY 4.0) | +40 °C 下合成压力负载降频（GPU 95.6 °C），YOLOv8s TensorRT FP16 推理平均 19.1 W（压力负载 36.5 W）且远低于降频温度；结论是合成压力高估推理的热与功耗需求 | 经 Crossref 摘要核；AGX Orin |
| D3 | Gong Y, et al. Lotus: learning-based online thermal and latency variation management for two-stage detectors on edge devices. arXiv, 2024-10-01 | arXiv:2410.10847 | OA | 重负载发热触发变频致时延不稳；强化学习协调 CPU/GPU 频率。Orin Nano | 摘要页已核；DAC'24 仅来自备注，待核 |
| D4 | Molleda J, Lema D G, Usamentiaga R. Edge deployment of YOLOv12 and YOLOv26 instance segmentation for real-time steel surface defect inspection. J Real-Time Image Proc 23(5): 181 (2026) | doi:10.1007/s11554-026-01974-1 | OA (CC BY 4.0) | RTX 5090、AGX Orin、Orin Nano；24 个模型，3,097 张图、13,318 个实例、8 类；FP16 下 YOLOv26 nano 在 Orin Nano 89.9 FPS，AGX Orin 146.7 FPS；INT8 分割引擎在 TensorRT 10.3 下两块 Jetson 上都建不出。摘要只报 FPS 和精度，无功耗、温度、P99 | Crossref 核；**非 Orin NX** |
| D5 | Le N-T, Bui C V. Real-Time Multi-Camera Edge AI on Jetson Orin NX: A Comprehensive Benchmark of DeepStream, TensorRT, and Lightweight Object Detection Pipelines. ICCITX 2026, pp. 46–51, IEEE | doi:10.1109/iccitx70146.2026.11679903 | 学校（IEEE） | 元数据由 Crossref 确认；**内容未读，不知是否测功耗/温度/P99** | 需你下载后判断 |
| D6 | Mishra A, Lone H. Beyond Benchmarks: Continuous Edge Inference for Fine-Grained Roadside Perception. arXiv, 2026-06-15 | arXiv:2606.17241 | OA | 流视频比静态图相对精度低约 20–30%；55 分钟路测 16.18 FPS，称在安全热限内。路侧场景，Orin Nano | 摘要页已核；非工业 |
| D7 | Chakraborty A, et al. Profiling Concurrent Vision Inference Workloads on NVIDIA Jetson – Extended. arXiv v1 2025-08-11，v2 2026-09-19 | arXiv:2508.08430 | OA | GPU 利用率可达 100% 而 SM/Tensor 核占用仅 15–30%；CPU 侧线程调度常是瓶颈 | 摘要页已核；板型未写 |
| D8 | 车身点焊缺陷 YOLOv8n，Applied Sciences 16(17): 8509 (2026) | mdpi.com/2076-3417/16/17/8509 | OA | 片段：AGX Orin，TensorRT FP16，56.26 FPS，平均端到端 17.77 ms | **作者、DOI 未取到，待核** |
| D9 | LDA-YOLO11（路面缺陷），Sci Rep (2026) | nature.com/articles/s41598-026-69844-1 | OA | 片段：Orin NX，TensorRT FP16，27 ms/张 | **作者待核；路面缺陷非制造业** |
| D10 | 绝缘子缺陷（Orin NX），World Scientific，疑为 IJPRAI | doi:10.1142/s0218001426590068 | 未知 | 只有 DOI | **内容未知，待核** |

**结论（我的判断）**：没找到经核实的、在 Orin NX 上同时报 P50/P99、功耗、温度的同行评审工业缺陷检测论文。D5、D9、D10 是 NX 相关但内容未核。
**缺口**：Xavier/TX2 热降频的同行评审论文；Jetson 时延尾部与预热方法论文。

## E. 查新（差距表四列）

四列：(1) 视觉缺陷检测；(2) 零件级有限样本高概率漏检保证；(3) 两级级联、双阈值联合校准；(4) 保证在量化/边缘引擎上验证。

**ALERT：两轮检索均未发现同时满足三列以上的工作。** 覆盖很薄：未直接查 Semantic Scholar、Google Scholar、IEEE Xplore、ScienceDirect；中文只跑了 2 组词，结果都是无关页面；不能据此说中文文献里没有。

| 引用 | ID | 覆盖列 | 区别 | 状态 |
|---|---|---|---|---|
| Hossen, Mistry, Kamal. Low Cost Two-Stage Fabric Defect Detection at the Edge. 2026-08-12 | arXiv:2608.14727 | 1；3 部分；4 部分 | 召回是 20 张缺陷图上的经验区间（0.83–1.00），无有限样本保证；FPR 49.3%（113/229）；加速主要归因于 JPEG 解码与推理重叠 | 摘要页已核 |
| Pona 等. Calibrate-Then-Delegate. 2026-04-15，修订 2026-08-21 | arXiv:2604.14251 | 3；2 部分 | LLM 安全监控；单目标有限样本保证；无量化或边缘验证 | 摘要页已核 |
| Ruan 等. Doomed from the Start. 2026-07-07，修订 2026-07-16 | arXiv:2607.06503 | 3；2 部分 | LLM 智能体早停；摘要未写共形或 LTT（该联系为子代理推断） | 摘要页已核 |
| Zhu 等. Conformalized LLMs under Configuration Shift. EMNLP 2026 | arXiv:2608.01460 | 4 部分（量化作为分布偏移） | LLM 预测集；摘要称量化常使经验覆盖低于目标 | 摘要页已核 |
| Shin. Is INT8 Portable? 2026-09-14 | arXiv:2609.16085 | 4（仅背景） | 无保证、无缺陷任务；INT8 仅共享整数核时完全一致，否则 958–965/1000；含 AGX Orin iGPU 与 NVDLA | 摘要页已核 |
| Shen, Liu. Conformal Segmentation in Industrial Surface Defect Detection. 2025-04-24；MDPI Mathematics 13(15): 2430 | arXiv:2504.17721 | 1；2 部分 | 像素级、期望意义；单模型无级联 | arXiv 页已核；MDPI 信息来自检索 |
| Huang, Park, Paoletti, Simeone. Reliable Inference in Edge-Cloud Model Cascades via Conformal Alignment. 2025-10-20，v3 2026-08-12，在审 | arXiv:2510.17543 | 3 | 保证是边缘决策达到云端条件覆盖的平均比例；CIFAR-100 与 TeleQnA；无量化或硬件 | 摘要页已核 |
| Sapoutzoglou 等. Trustworthy Visual Quality Inspection under Data Scarcity in Manufacturing. GECON 2026 | arXiv:2608.21967 | 1；3 松散 | 扩散模型合成缺陷样本；无形式化界；进行中工作 | 摘要页已核 |
| Yang, Wang. SafeRestore. 2026-09-03 | arXiv:2609.03475 | 1；2 部分 | 对路由策略给"两个单侧精确二项界"，风险是相对检测器的，不是真缺陷召回；主策略五次训练重复中仅一次通过认证 | 摘要页已核 |
| 车间异常检测 FDR，Int J Adv Manuf Technol，doi:10.1007/s00170-026-19191-2（旧稿记为 "Yan, Sun 2026"） | — | 1；2 部分 | 保证对象是被标记零件中的误报比例，不是漏检 | **仅检索片段；Springer 页要求登录，作者、日期、刊物均未核；"Yan, Sun" 署名来自旧稿，不是本轮核到的** |

仅检索片段、未打开（待核）：arXiv:2505.24038（共形目标检测序贯风险控制）、2304.06052、2605.07549、2607.27143（成本敏感共形预测与人工复检）、2606.15153、2607.25018（LLM 多层共形级联）、2512.20012（电信边云专家级联）、2510.08748（共形风险训练）；Neyman–Pearson umbrella 相关 1608.03109、1802.02557、2112.00314、2607.03590。

---

## 需要你本人核对或下载后判断的

1. Kang 2606.16106 正文：找小模型满频对最低可行频率的能耗数字。找不到就要从方向说明里删掉这一说法。
2. Raju 2608.11770 正文：94% 到底来自手动动态范围还是 QAT。
3. NVIDIA 三个页面（C8 版本号、D1 的 °C、B6 的 TensorRT 版本）对原页。
4. D5（IEEE，学校权限）：是否测功耗、温度、P99。
5. 十个标"待核"的条目（A6 日期、A9、D8–D10、B5、C10 等）。
