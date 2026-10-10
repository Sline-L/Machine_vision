# 核查：英文期刊/会议资质与分区（一级指标）

- 核查对象：文献综述引用的 13 条英文 venue（对应 task-1 清单）
- 核查日期：2026-10-08
- 核查人：venue-checker（Team 子任务 task-1）
- 原则：**每条指标均给出实际访问过的来源；查不到写「未查到」，不用记忆或推测填充。**
- 版本：v2（补充 EI 收录核验、2020 版预警名单逐刊值、PaDiM 出处卷次核验）

## 0. 来源分级与方法说明（重要）

| 级别 | 含义 | 本报告中的例子 |
| --- | --- | --- |
| A 官方 | 出版商官网、学会官网、会议论文集原文页 | Springer 期刊页（link.springer.com，含「Abstracted and indexed in」列表）、中国人工智能学会 caai.cn、Springer LNCS 论文页、CCF《推荐国际学术会议和期刊目录（2026年）》原文 PDF、arXiv 摘要页 |
| B 权威第三方（机构平台） | 中科院文献情报中心「全球科技期刊集成平台」（jbest.las.ac.cn），逐刊标注 EI 收录 / SCI 收录 | 用于 EI 与 SCI 收录状态的交叉核验 |
| C 第三方聚合 | 数据可能与官方存在时差，必须标注 | LetPub（letpub.com.cn / letpub.tw / letpub.com）、BioxBio |

已知核查限制（如实记录，影响结论强度）：

1. **EI 收录**：8 本期刊中 6 本已核到可引用来源（Sensors、Materials、AIR、JIM、CAAI Trans.、Computers in Industry = 是；Scientific Data = 否）；**Applied Sciences（MDPI）在中科院文献情报中心平台按 ISSN 2076-3417 及刊名检索均无对应记录 → 写「未查到」**。4 个**会议**（CVPR/NeurIPS/MICCAI/ICPR）的 EI/Compendex 收录状态**未查到**——该平台只覆盖期刊，会议论文集的 Compendex 状态需 Engineering Village 授权源核验。
2. **中科院分区**取自 LetPub 第三方页面（《新锐期刊分区表》2026年3月版、《期刊分区表》2025年3月升级版、《期刊分区表》2023年12月升级版三个口径，取页面实际显示值）。中科院分区表官网（fenqubiao.com）需机构登录，未直接核验。
3. **JCR 分区/IF**：LetPub 页面「2025-2026 年最新版 WOS 分区」需登录才显示；本报告 JCR 分区取自 LetPub 英文站公开的 WOS Quartile（该站未标注年份，其繁体站同源页标注为 **2023–2024**，第三方数据、可能滞后一个版本）；JCR IF 取自 BioxBio（标注 2025 = "2026 update"）与期刊官网自报值，二者不一致时同时记录。
4. **MDPI 官网（mdpi.com）403**，故 MDPI 三刊无「官网自报 IF」可比对，仅有第三方值。
5. 表内「来源URL」列使用编号 `[n]`，完整 URL 见第 5 节来源清单。

## 1. 主表（13 条 venue）

| venue | SCIE | EI | JCR分区 | JCR IF(年份) | 中科院分区 | 领域地位 | 风险信号 | 来源URL |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Sensors (MDPI) [3] Saiz 2022、[4]/[6] Allam 2021、[14] SU 2026 | 是（LetPub 收录表 SCIE；中科院文献情报中心平台「SCI收录：是」；DOAJ 亦收录） | **是**（中科院文献情报中心平台，ISSN 1424-8220：「EI收录：是」） | Q2（JIF）：分析化学 Q2 37/110；工程:电子与电气 Q2 127/369；仪器仪表 Q2 24/81（LetPub 英文站 WOS Quartile，年份未标注；繁体站同源页标注 2023–2024；2025–2026 最新版需登录，未查到） | **4.0（2025，"2026 update"，BioxBio）**；3.5（2024，BioxBio）；LetPub 页标题写作 3.500（=2024 值）；官网自报值未查到（mdpi.com 403） | 2025年3月升级版：大类 综合性期刊 **3区**；小类 分析化学 **3区**、工程:电子与电气 **3区**、仪器仪表 **3区**；非 Top。2023年12月升级版：大类 3区，小类 分析化学 2区、其余 3区。2026年3月新锐版：大类 3区，小类 分析化学 2区、其余 3区。 | 传感器/仪器领域主流开放获取综合刊；发文量 7884 篇/年（LetPub），非领域顶刊 | **有**：MDPI 出版社；**2020 版中科院国际期刊预警名单「预警等级：低」**（2021 版起不在名单）；年发文量极大（7884 篇）；自引率 7.5%（2025-26 口径）/ 11.80%（2023-24 口径） | [1][9][10][20][21][22] |
| Artificial Intelligence Review (Springer) [2] Ma 2024 | 是（LetPub 收录表 SCIE；中科院文献情报中心平台「SCI收录：是」） | **是**（Springer 官网「Abstracted and indexed in」列表含 **EI Compendex**；中科院文献情报中心平台「EI收录：是」） | Q1（JIF）：计算机:人工智能 Q1 6/210（LetPub 英文站 WOS Quartile；年份未标注，第三方） | **18.8（2025，官网自报 = BioxBio 一致）**；13.9（2024，BioxBio；LetPub 页标题 13.900 = 2024 值）；官网 5 年 IF 19.1（2025） | 2025年3月升级版：大类 计算机科学 **1区**、Top 期刊 是；小类 计算机:人工智能 **2区**。2023年12月升级版：大类 2区、小类 2区、Top 是。2026年3月新锐版：大类 1区、小类 1区、Top 是 | AI 领域高影响综述型期刊；CiteScore 36.1（LetPub 英文站） | 无预警记录（2020–2026 各版均不在预警名单）。注意：年度 IF 波动大（2023: 10.7 → 2024: 13.9 → 2025: 18.8）；Springer 转全 OA 后发文量与 APC 上升 | [2][9][11][15][22] |
| Materials (MDPI) [1] Liu 2020 ConCNN | 是（LetPub 收录表 SCIE；中科院文献情报中心平台「SCI收录：是」；DOAJ 亦收录） | **是**（中科院文献情报中心平台，ISSN 1996-1944：「EI收录：是」） | Q2（JIF）：材料科学:综合 Q2 236/472；冶金工程 Q2 25/97；物理:应用 Q2 70/191；物理化学 Q3 97/191（LetPub 英文站，年份未标注，第三方） | **3.7（2025，BioxBio）**；3.2（2024，BioxBio；LetPub 页标题 3.200 = 2024 值）；官网自报值未查到（mdpi.com 403） | 2025年3月升级版：大类 材料科学 **3区**；小类 材料科学:综合 **4区**、冶金工程 3区、物理:应用 3区、物理:凝聚态 3区；非 Top。2023年12月升级版：大类 3区，材料科学:综合 4区。2026年3月新锐版：大类 3区，各小类均 3区 | MDPI 材料类综合刊，发文量极大 | **有**：MDPI 出版社；**2020 版中科院国际期刊预警名单「预警等级：低」**；2025 升级版小类「材料科学:综合」为 4区；自引率 8.1% | [3][9][12][22] |
| Applied Sciences (MDPI) [2] Nagy 2022 | 是（LetPub 收录表 SCIE；DOAJ 亦收录） | **未查到**（中科院文献情报中心平台按 ISSN 2076-3417 及刊名检索均无对应记录） | Q2（JIF，综合档）：工程:综合 Q2 55/178；化学:综合 Q3 127/250；材料科学:综合 Q3 286/472；物理:应用 Q3 96/191（LetPub 英文站，年份未标注，第三方） | 2.5（LetPub 页标题 2.500 = 2024 值）；**2025 值未查到**（BioxBio 未检索到该刊页面，未用推测补） | 2025年3月升级版：大类 综合性期刊 **4区**；小类 化学:综合 4区、工程:综合 4区、材料科学:综合 4区、物理:应用 4区；非 Top。2023年12月升级版：大类 4区（化学:综合 3区）。2026年3月新锐版：大类 3区，各小类均 3区 | MDPI 综合工程刊，发文量极大，学术门槛低，属「可发表但不宜作为框架引用」的典型 | **有**：MDPI 出版社；**2020 版中科院国际期刊预警名单「预警等级：低」**；2025 升级版大类 4区；自引率 6.9%；发文量极大 | [4][9] |
| IEEE/CVF CVPR [5] Redmon 2016 YOLO、[9] Bergmann 2019 MVTec AD、[11] Roth 2022 PatchCore、[15] Lin 2017 FPN | 不适用（会议论文集，非期刊） | 未查到（会议论文集，Compendex 状态需 Engineering Village 授权源） | 不适用（JCR 只评期刊） | 不适用 | 不适用（中科院分区表针对期刊；2026 新锐分区收录 15 种计算机会议论文集，**CVPR 是否被收录未查到**） | **领域顶级会议**：CCF《推荐国际学术会议和期刊目录（2026年）》「人工智能」**A 类**会议；计算机视觉领域公认顶会 | 无（会议正刊论文）；提示：CVPR 属会议，不能用 JCR/中科院分区描述，应写「CCF A 类 / 领域顶级会议」 | [17] |
| NeurIPS (NIPS) [4] Ren 2015 Faster R-CNN | 不适用（会议论文集，非期刊） | 未查到（同上） | 不适用 | 不适用 | 不适用 | **领域顶级会议**：CCF（2026 年目录）「人工智能」**A 类**会议；机器学习领域公认顶会 | 无；引用时写「CCF A 类 / 领域顶级会议」，不要用分区描述 | [17] |
| MICCAI (Springer LNCS) [7] Ronneberger 2015 U-Net | 不适用（会议论文集，Springer LNCS） | 未查到（同上） | 不适用 | 不适用 | 不适用 | CCF（2026 年目录）「交叉/综合/新兴」**B 类**会议；医学影像计算领域权威会议，U-Net 原始出处 | 无；属 CCF B 类（非 A 类），但为该子领域奠基性论文的正式出处 | [17] |
| ICPR Workshops (Springer LNCS) [10] Defard 2021 PaDiM | 不适用（会议论文集） | 未查到（同上） | 不适用 | 不适用 | 不适用 | **已核实：PaDiM 发表于《Pattern Recognition. ICPR International Workshops and Challenges (ICPR 2021)》，Springer LNCS，First Online 2021-03-05, pp. 475–，DOI 10.1007/978-3-030-68799-1_35**。ICPR **主会**为 CCF（2026 年目录）「人工智能」**C 类**会议；workshop 论文评审强度与索引覆盖低于主会正刊 | **有（引用口径风险）**：PaDiM 确为 ICPR **Workshop** 论文（已核实），不是 ICPR 主会论文；引用时应明确标注 workshop 出处，或同时引用其 arXiv 版本/后续期刊版本以增强证据力 | [17][24] |
| Journal of Intelligent Manufacturing (Springer) [8] Tabernik 2020 | 是（LetPub 收录表 SCIE；Springer 官网「Abstracted and indexed in」列表含 Science Citation Index Expanded (SCIE)；中科院文献情报中心平台「SCI收录：是」） | **是**（Springer 官网「Abstracted and indexed in」列表含 **EI Compendex**；中科院文献情报中心平台「EI收录：是」） | Q1（JIF）：计算机:人工智能 Q1 37/210；工程:制造 Q1 13/71（LetPub 英文站，年份未标注，第三方） | **7.7（2025，官网自报 = BioxBio 一致）**；7.4（2024，BioxBio；LetPub 页标题 7.400 = 2024 值）；官网 5 年 IF 9.2（2025） | 2025年3月升级版：大类 工程技术 **2区**；小类 计算机:人工智能 2区、工程:制造 3区；非 Top。2023年12月升级版：大类 2区。2026年3月新锐版：大类 2区 | 智能制造 / 工业人工智能领域权威期刊（Springer），表面缺陷检测方法论文的常见正式出处 | 无预警记录（2020–2026 各版均不在预警名单）；自引率 7.8% | [5][9][13][16][22] |
| Scientific Data (Nature Portfolio) [13] Wu 2025 | 是（LetPub 收录表 SCIE；中科院文献情报中心平台「SCI收录：是」；DOAJ 亦收录） | **否**（中科院文献情报中心平台：「EI收录：否」「Medline收录：是」） | Q1（JIF）：综合性期刊 Q1 17/140（LetPub 英文站，年份未标注，第三方） | 6.9（LetPub 页标题 6.900 = 2024 值）；**2025 值未查到**（nature.com/sdata 页面正文未含 IF 文本，BioxBio 未检索到该刊页面） | 2025年3月升级版：大类 综合性期刊 **2区**，非 Top。2023年12月升级版：大类 2区。**2026年3月新锐版：大类 2区，Top 期刊 是** | Nature Portfolio 数据类期刊，数据集论文（Data Descriptor）权威平台 | 无预警记录（2020–2026 各版均不在预警名单）。风险提示：论文类型为数据描述，引用价值在数据集/基准，不在方法框架；**EI 未收录**；APC 高 | [6][9][22] |
| CAAI Transactions on Intelligence Technology (IET/Wiley) [16] Ding 2019 TDD-Net | 是（LetPub 收录表 SCIE；中国人工智能学会官网：「已被 SCIE、Ei Compendex、Scopus、DOAJ、GoOA、INSPEC 等国际知名数据库收录」；DOAJ 亦收录） | **是**（中国人工智能学会官网明列 **Ei Compendex**；中科院文献情报中心平台「EI收录：是」） | Q2（JIF）：计算机:人工智能 Q2 65/210（LetPub 英文站，年份未标注，第三方） | 7.3（LetPub 页标题 7.300 = 2024 值）；**2025 值未查到**（Wiley 官网 403） | 2025年3月升级版：大类 计算机科学 **1区**、Top 期刊 **是**；小类 计算机:人工智能 **1区**。2023年12月升级版：大类 2区，小类 3区。2026年3月新锐版：大类 1区，小类 2区 | 中国人工智能学会（CAAI）会刊，IET/Wiley 出版；入选 2023 年度中国科技期刊卓越行动计划高起点新刊 | **有（轻微）**：2023→2025 分区跃升快（大类 2区→1区）、中国主办英文刊发文量增长快；无预警记录（2020–2026 各版均不在预警名单） | [7][9][22][23] |
| Computers in Industry (Elsevier) [17] Božič 2021 | 是（LetPub 收录表 SCIE；中科院文献情报中心平台「SCI收录：是」） | **是**（中科院文献情报中心平台：「EI收录：是」） | Q1（JIF）：计算机:跨学科应用 Q1 18/185（LetPub 英文站，年份未标注，第三方） | **10.0（2025，BioxBio）**；9.1（2024，BioxBio；LetPub 页标题 9.100 = 2024 值）；官网自报值未查到（sciencedirect 403） | 2025年3月升级版：大类 计算机科学 **1区**、Top 期刊 **是**；小类 计算机:跨学科应用 **2区**。2023年12月升级版：大类 1区。2026年3月新锐版：大类 1区，Top 是 | 工业信息化 / 智能制造领域老牌权威期刊（Elsevier），工业视觉检测方法论文的重要出处 | 无预警记录（2020–2026 各版均不在预警名单）；自引率 7.0% | [8][9][14][22] |
| arXiv 预印本 [3] Arikan 2019, arXiv:1904.04671 | **否**（预印本平台，非期刊，无 SCIE 收录） | 否 | 不适用 | 不适用 | 不适用 | **预印本，未经同行评审**；《Surface Defect Classification in Real-Time Using Convolutional Neural Networks》 | **有（高）**：arXiv 页面无 journal-ref、无正式 DOI（仅 arXiv 的 DataCite DOI 10.48550/arXiv.1904.04671）；OpenAlex 中该文类型为 `preprint`、来源为 arXiv，条目下未见正式发表版；v1 于 2019-04-07 提交后无更新版本。**未查到正式发表版** → 综述中须明确标注为预印本，或替换为正式发表来源 | [18][19] |

## 2. 官网自报 IF 与第三方 JCR 数据的一致性核对（硬性要求 2）

| venue | 官网自报 | 第三方（LetPub 页标题 / BioxBio） | 是否一致 | 说明 |
| --- | --- | --- | --- | --- |
| Artificial Intelligence Review | **18.8（2025）**，5 年 IF 19.1（2025）— Springer 官网 | BioxBio 18.8（2025）；13.9（2024）；LetPub 页标题 13.900 | **一致（2025）**，与 LetPub 标题（=2024 值）**不一致** | LetPub 页标题仍停留在 2024 值（13.9），若照抄 LetPub 会得到过时数字 |
| Journal of Intelligent Manufacturing | **7.7（2025）**，5 年 IF 9.2（2025）— Springer 官网 | BioxBio 7.7（2025）；7.4（2024）；LetPub 页标题 7.400 | **一致（2025）**，与 LetPub 标题（=2024 值）**不一致** | 同上，存在 1 个版本时差 |
| Sensors | 未查到（mdpi.com 403） | BioxBio 4.0（2025）/ 3.5（2024）；LetPub 页标题 3.500 | 无法比对 | 第三方之间也不一致（4.0 vs 3.5），差异来自年份口径 |
| Materials | 未查到（mdpi.com 403） | BioxBio 3.7（2025）/ 3.2（2024）；LetPub 页标题 3.200 | 无法比对 | 同上 |
| Applied Sciences | 未查到（mdpi.com 403） | LetPub 页标题 2.500（=2024）；2025 未查到 | 无法比对 | — |
| Scientific Data | 未查到（nature.com 页面正文无 IF 文本） | LetPub 页标题 6.900（=2024）；2025 未查到 | 无法比对 | — |
| CAAI Trans. Intelligence Technology | 未查到（Wiley 403） | LetPub 页标题 7.300（=2024）；2025 未查到 | 无法比对 | — |
| Computers in Industry | 未查到（sciencedirect 403） | BioxBio 10.0（2025）/ 9.1（2024）；LetPub 页标题 9.100 | 无法比对 | — |

**结论：本次唯一可做双向核对的 2 本 Springer 期刊，官网 2025 值（18.8 / 7.7）与 BioxBio 2025 值完全一致；而 LetPub 页面标题显示的 IF（13.900 / 7.400）是上一版（2024）数值。综述中若引用 LetPub 数字，会低估这两本刊。**

## 3. 风险信号汇总（含一句话理由）

| venue | 风险等级 | 一句话理由 |
| --- | --- | --- |
| arXiv:1904.04671（Arikan 2019） | 高 | 纯预印本、无同行评审、无 journal-ref，OpenAlex 中亦仅有 preprint 记录，未查到正式发表版 |
| Sensors (MDPI) | 中 | MDPI 出版社 + 2020 版中科院预警名单「预警等级：低」+ 年发文量 7884 篇 |
| Materials (MDPI) | 中 | MDPI 出版社 + 2020 版中科院预警名单「预警等级：低」+ 2025 升级版小类「材料科学:综合」4区 + 发文量极大 |
| Applied Sciences (MDPI) | 中 | MDPI 出版社 + 2020 版中科院预警名单「预警等级：低」+ 2025 升级版大类 4区 + 门槛低 |
| ICPR Workshops（PaDiM 出处） | 中（引用口径） | 已核实 PaDiM 为 ICPR 2021 **Workshop** 论文集论文（非主会）；ICPR 主会仅 CCF C 类，workshop 论文影响力/索引更弱 |
| CAAI Trans. Intelligence Technology | 低 | 2023→2025 中科院大类 2区→1区跃升快，中国主办英文刊发文量增长快（无预警记录） |
| Scientific Data | 低 | 无论文质量预警，但属数据描述类论文且 **EI 未收录**，方法学引用价值有限 |
| CVPR / NeurIPS / MICCAI / JIM / Computers in Industry / AI Review | 无（就预警与收录而言） | 均在 2020–2026 各版中科院预警/新锐 Under Review 名单之外（LetPub 页面显示），且为 CCF A/B 类会议或 Q1 期刊 |

## 4. 独立判断：哪些 venue 足以支撑综述的奠基性/框架性引用

**A. 可作为奠基性/框架性引用（方法源头、领域公认）**

1. **CVPR（CCF A 类）** — YOLO、FPN、MVTec AD、PatchCore 均为方法/基准的原始出处，是缺陷检测方法学主干的正当来源。引用时标注「CCF A 类会议 / 计算机视觉顶级会议」。
2. **NeurIPS（CCF A 类）** — Faster R-CNN 的方法源头，框架性引用成立。
3. **MICCAI（CCF B 类）** — U-Net 是分割网络结构的奠基工作，虽为 B 类，但作为该结构的**原始出处**必须引用正刊。
4. **Computers in Industry（Elsevier，Q1，中科院 2025 大类 1区 / Top，EI+SCIE 双收录）**、**Journal of Intelligent Manufacturing（Springer，Q1，中科院 2025 大类 2区，EI+SCIE 双收录）** — 工业视觉检测/智能制造方向的权威期刊，可支撑「工业缺陷检测技术演进」「智能制造背景」这类框架性论述。
5. **Artificial Intelligence Review（Springer，Q1，中科院 2025 大类 1区 / Top，EI+SCIE 双收录）** — 综述型高影响期刊，适合作为「领域研究现状/综述结论」的框架性依据（注意用 2025 年值 18.8，不要用 LetPub 的 13.9）。

**B. 只适合作为具体案例证据（不适合承重）**

1. **Sensors / Materials / Applied Sciences（MDPI 三刊）** — 理由：发文量极大（Sensors 7884 篇/年）、Applied Sciences 在 2025 升级版为 4区、**三刊在 2020 版中科院预警名单中均为「预警等级：低」**，且均为「宽口径综合刊」。它们可以支撑「某类传感器方案/某种材料表面检测的具体实现」这类**案例与工程细节**，但若综述的方法学主干（框架、演进脉络、结论性判断）主要依赖这三刊，容易被评审判定为「参考论文含金量不足」。
2. **CAAI Transactions on Intelligence Technology** — 近两年分区跃升、发文增长快；作为「补充案例/国内团队工作」可以，作为奠基引用不稳。
3. **Scientific Data** — 提供数据集/基准（如工业缺陷数据集）时引用恰当；不要用它支撑方法学结论（且 EI 未收录）。
4. **ICPR Workshop 版本（PaDiM）** — 仅作为「方法早期版本」引用，须明确标注 workshop 出处；建议同时引用 arXiv 版本或后续正式版本，避免评审质疑出处权威性。
5. **arXiv:1904.04671** — 只能作为「早期探索/工程实践案例」，且必须在正文与参考文献中明确标注为预印本；本次核查未查到其正式发表版。若综述需要这条证据，建议优先替换为同主题的正式发表论文。

**C. 对项目方的总体判断**

- 13 条 venue 中，**严格意义的「领域顶级」为 2 个（CVPR、NeurIPS，CCF A 类）**；若把子领域权威会议 MICCAI（CCF B 类）计入则为 **3 个**。
- **Q1 期刊 4 本**：Artificial Intelligence Review、Journal of Intelligent Manufacturing、Scientific Data、Computers in Industry（另有 CAAI Transactions 在 2025 升级版为 1区 / JCR Q2）。
- **EI + SCIE 双收录的期刊共 6 本**：Sensors、Materials（两者为 MDPI）、Artificial Intelligence Review、Journal of Intelligent Manufacturing、CAAI Trans. Intelligence Technology、Computers in Industry；**Scientific Data 仅 SCIE（EI 未收录）**；Applied Sciences 的 EI 状态未查到。
- **风险集中点**：MDPI 三刊（均含 2020 版预警记录）+ 1 篇 arXiv 预印本 + 1 条 ICPR Workshop 口径，合计覆盖引用 [1][2][3][4][6][14][10] 多条。建议把「框架性结论」的支撑引用转移到 CVPR/NeurIPS/MICCAI/Computers in Industry/JIM/AI Review，把 MDPI 与 arXiv 限定在具体案例与数据来源位置。

## 5. 来源清单（表内编号对应）

| 编号 | 来源 | URL | 级别 |
| --- | --- | --- | --- |
| [1] | LetPub 期刊详情：SENSORS（SCIE/Scopus/DOAJ 收录、中科院 2025/2023/2026新锐分区、2020–2026 预警名单逐版值、自引率、年文章数、实时/五年 IF） | https://www.letpub.com.cn/index.php?journalid=7473&page=journalapp&view=detail | 第三方 |
| [2] | LetPub 期刊详情：ARTIFICIAL INTELLIGENCE REVIEW | https://www.letpub.com.cn/index.php?journalid=894&page=journalapp&view=detail | 第三方 |
| [3] | LetPub 期刊详情：Materials | https://www.letpub.com.cn/index.php?journalid=8625&page=journalapp&view=detail | 第三方 |
| [4] | LetPub 期刊详情：Applied Sciences-Basel | https://www.letpub.com.cn/index.php?journalid=9954&page=journalapp&view=detail | 第三方 |
| [5] | LetPub 期刊详情：JOURNAL OF INTELLIGENT MANUFACTURING | https://www.letpub.com.cn/index.php?journalid=4698&page=journalapp&view=detail | 第三方 |
| [6] | LetPub 期刊详情：Scientific Data | https://www.letpub.com.cn/index.php?journalid=10198&page=journalapp&view=detail | 第三方 |
| [7] | LetPub 期刊详情：CAAI Transactions on Intelligence Technology | https://www.letpub.com.cn/index.php?journalid=14628&page=journalapp&view=detail | 第三方 |
| [8] | LetPub 期刊详情：COMPUTERS IN INDUSTRY | https://www.letpub.com.cn/index.php?journalid=2017&page=journalapp&view=detail | 第三方 |
| [9] | LetPub 英文站 WOS Quartile（JCR 分区，第三方；年份未标注，繁体站同源页标注 2023–2024）。URL 模式：`https://www.letpub.com/index.php?journalid=<jid>&page=journalapp&view=detail`，jid = 7473/894/8625/9954/4698/10198/14628/2017 | https://www.letpub.com/index.php?journalid=7473&page=journalapp&view=detail | 第三方 |
| [10] | BioxBio：Sensors IF 历史 | https://www.bioxbio.com/journal/SENSORS-BASEL | 第三方 |
| [11] | BioxBio：Artificial Intelligence Review IF 历史 | https://www.bioxbio.com/journal/ARTIF-INTELL-REV | 第三方 |
| [12] | BioxBio：Materials IF 历史 | https://www.bioxbio.com/journal/MATERIALS | 第三方 |
| [13] | BioxBio：Journal of Intelligent Manufacturing IF 历史 | https://www.bioxbio.com/journal/J-INTELL-MANUF | 第三方 |
| [14] | BioxBio：Computers in Industry IF 历史 | https://www.bioxbio.com/journal/COMPUT-IND | 第三方 |
| [15] | Springer 官网期刊页：Artificial Intelligence Review（Impact Factor 18.8 (2025)、5-year 19.1 (2025)；「Abstracted and indexed in」含 EI Compendex、SCIE、SCOPUS 等） | https://link.springer.com/journal/10462 | 官方 |
| [16] | Springer 官网期刊页：Journal of Intelligent Manufacturing（Impact Factor 7.7 (2025)、5-year 9.2 (2025)；「Abstracted and indexed in」含 EI Compendex、Science Citation Index Expanded (SCIE)、SCOPUS 等） | https://link.springer.com/journal/10845 | 官方 |
| [17] | CCF《推荐国际学术会议和期刊目录（2026年）》（第七版正式版）PDF 原文：CVPR = 人工智能 A 类；NeurIPS = 人工智能 A 类；ICPR = 人工智能 C 类；MICCAI = 交叉/综合/新兴 B 类 | PDF：https://lib.zjgsu.edu.cn/_upload/article/files/f5/b1/f4f7201343b88c0f10564f590ebe/854a3c68-36a6-4698-a359-5184d5e30a0c.pdf ；发布页：https://lib.zjgsu.edu.cn/2026/0414/c1056a221631/page.htm | 官方（学会目录，高校镜像） |
| [18] | arXiv 摘要页：arXiv:1904.04671（v1, 2019-04-07；Comments: Supplementary material will follow；无 journal-ref） | https://arxiv.org/abs/1904.04671 | 官方 |
| [19] | OpenAlex API：按标题检索该文，唯一匹配为 type=preprint、来源 arXiv（无正式发表版记录） | https://api.openalex.org/works?search=Surface%20Defect%20Classification%20in%20Real-Time%20Using%20Convolutional%20Neural%20Networks | 第三方 |
| [20] | DOAJ API：Sensors（ISSN 1424-8220）收录与评审方式 | https://doaj.org/api/search/journals/issn%3A1424-8220 | 第三方（DOAJ 官方 API） |
| [21] | LetPub 繁体站：SENSORS 页（WOS 四分位标注为「2023-2024」、自引率 11.80%） | https://www.letpub.tw/index.php?journalid=7473&page=journalapp&view=detail | 第三方 |
| [22] | 中国科学院文献情报中心「全球科技期刊集成平台」（jbest.las.ac.cn）逐刊详情页：EI收录 / SCI收录 / Medline收录 字段。已核：SENSORS（ISSN 1424-8220，EI 是、SCI 是、Medline 是，id=42668）；MATERIALS（ISSN 1996-1944，EI 是、SCI 是，id=44825）；ARTIFICIAL INTELLIGENCE REVIEW（ISSN 0269-2821，EI 是、SCI 是，id=40135）；JOURNAL OF INTELLIGENT MANUFACTURING（ISSN 0956-5515，EI 是、SCI 是，id=40893）；SCIENTIFIC DATA（ISSN 2052-4463，EI 否、SCI 是，id=45454）；CAAI TRANSACTIONS ON INTELLIGENCE TECHNOLOGY（EI 是、SCI 是，id=1377963）；COMPUTERS IN INDUSTRY（ISSN 0166-3615，EI 是、SCI 是，id=38457）。检索入口为 POST `/journal/global_search_result_page`（`search_condit=title=<刊名>\|` 或 `pissn=<ISSN>\|`）；Applied Sciences (MDPI, ISSN 2076-3417) 无匹配记录 | 检索页：http://jbest.las.ac.cn/journal/index ；示例详情页：http://jbest.las.ac.cn/welcome/journal_detail?id=42668 | 权威第三方（中科院文献情报中心） |
| [23] | 中国人工智能学会（CAAI）官网：CAAI Transactions on Intelligence Technology 介绍页——「目前已被 SCIE、Ei Compendex、Scopus、DOAJ、GoOA、INSPEC 等国际知名数据库收录，入选 2023 年度中国科技期刊卓越行动计划高起点新刊项目」 | https://www.caai.cn/site/content/3883.html | 官方（学会） |
| [24] | Springer LNCS 论文页：Defard et al., "PaDiM: A Patch Distribution Modeling Framework for Anomaly Detection and Localization"，收录于 *Pattern Recognition. ICPR International Workshops and Challenges (ICPR 2021)*，First Online 2021-03-05, pp. 475–，DOI 10.1007/978-3-030-68799-1_35（证实为 workshop 论文集论文） | https://link.springer.com/chapter/10.1007/978-3-030-68799-1_35 | 官方 |

## 6. 「未查到」字段汇总（供后续补核，勿推测填充）

| 待补字段 | 涉及 venue | 补核建议途径 |
| --- | --- | --- |
| EI / Compendex 收录状态 | **Applied Sciences（MDPI）**；以及 4 个会议 CVPR / NeurIPS / MICCAI / ICPR Workshops | Engineering Village（Compendex）授权源列表；会议论文集需查 IEEE Xplore / Springer LNCS 卷次的 Compendex 覆盖说明 |
| JCR IF 2025（官方口径） | Sensors、Materials、Applied Sciences、Scientific Data、CAAI Trans. | JCR（Clarivate）订阅库；或期刊官网 Journal metrics 页（MDPI 官网本次 403） |
| JCR 分区最新版（2025-2026） | 全部期刊 | JCR 订阅库；LetPub 该栏需登录 |
| 官网自报 IF | Sensors、Materials、Applied Sciences、Scientific Data、CAAI Trans.、Computers in Industry | 对应出版商官网（本次 mdpi.com / sciencedirect / Wiley 均 403） |
| CVPR 是否被 2026 新锐分区收录为「重要会议论文集」 | CVPR（及 NeurIPS/MICCAI/ICPR） | 《新锐期刊分区表》2026 官网/公众号 |
| PaDiM 后续正式发表版（期刊版） | ICPR Workshops（PaDiM） | OpenAlex / Semantic Scholar 追踪该文后续版本（当前仅见 LNCS workshop 版与 arXiv 版） |
| 中科院分区表官方原始数据 | 全部期刊 | 中科院文献情报中心期刊分区表官网（需机构登录） |
