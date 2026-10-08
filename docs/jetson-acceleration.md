# Jetson 加速研究：推理路径审计、测量方案与验收标准

本文回答导师提出的三个问题：GearPro 的负载为什么适合 Jetson Orin NX、项目如何利用它的
硬件（GPU Tensor Core、2 个 DLA、CPU/GPU 共享内存、TensorRT FP16/INT8），以及如何在
**精度不变**的前提下与 RTX 4060 Laptop、CPU 比较延迟和功耗。

> 状态：导出、基准和验收脚本已实现，并已在开发机 CPU 上跑通流程；**尚未在 NX 上运行**。
> 本文不含任何 NX 新测量结果。除“已有基线”一节引用团队已有记录外，所有加速效果都是
> 待验证的假设，结果表必须由团队在 NX 上实测后填写。

## 1. 已有基线（团队已测，非本次新增）

来源：`srtp` 分支 HEAD `2c79075`（`docs/edgemedic-experiments.md` 的 Stage C 记录），
数据集回放 40 帧、60 s，**只含定位 + Scratch 子系统**：

| 指标 | PyTorch `.pt` | 定位改 TensorRT FP16 |
| --- | --- | --- |
| 定位 p95 | 65.0 ms | 26.7 ms |
| Scratch 子系统 p95 | ≈181–197 ms（主要瓶颈） | 未改动，仍为 `.pt` |
| 总 p95 | 244.2 ms | 219.9 ms |

Missing Hole 子系统从未在 NX 上计时；当前生产路径（两个专项子系统都启用）的端到端延迟
因此**未知**，是本研究要补的第一项数据。

## 2. 为什么这个负载适合 Jetson，以及项目如何利用它

Orin NX 16GB 的主要硬件（据 NVIDIA 模块数据手册；以实际模块和 JetPack 版本为准，
运行时用 `nvpmodel -q` 记录功耗模式）：

| 单元 | 规格 | 本项目中的用途 |
| --- | --- | --- |
| GPU | Ampere 架构，1024 CUDA core，32 个第三代 Tensor Core | 定位与两个 YOLO 检测器；FP16/INT8 走 Tensor Core |
| DLA | 2 × NVDLA v2.0，固定功能卷积加速器，支持 FP16/INT8 | 候选：四个分类器（EfficientNet-B0、ResNet18） |
| CPU | 8 核 Arm Cortex-A78AE | 采集、ROI 裁剪、PIL/ToTensor 预处理、Python 调度 |
| 内存 | 16 GB LPDDR5，128 bit，CPU 与 GPU/DLA 共用同一物理 DRAM | 所有张量；“显存”即系统内存 |
| 功耗 | 可配置功耗模式（10/15/25 W 等） | 用 VDD_IN 计算每件能耗 |

作为对照，RTX 4060 Laptop 是独立显卡（AD107，3072 CUDA core，96 个第四代 Tensor Core，
8 GB GDDR6，整卡功耗由笔记本厂商设定在约 35–115 W），CPU 与 GPU 之间需经 PCIe 拷贝。

### 2.1 加速来自哪里（假设，待实测验证）

1. **Tensor Core 需要低精度算子才被充分利用。** PyTorch 默认 FP32；在 Ampere 上 cuDNN
   卷积默认允许 TF32，因此现有 `.pt` 路径的卷积可能已经部分使用 Tensor Core。TensorRT
   FP16 的收益因此不只是“用上 Tensor Core”，而是：FP16 吞吐高于 TF32、权重与激活的
   内存流量减半、层融合（Conv+BN+激活）、按本机 GPU 自动选核。
2. **batch=1 的小网络受框架开销限制。** EfficientNet-B0 层数多、每层计算量小；PyTorch
   每层一次 Python/CUDA 调度，A78AE 上的 CPU 调度时间可能与 GPU 计算同量级。TensorRT
   把整网编成一个 engine，一次 `enqueue`。这一点需用 Nsight Systems 看 GPU 空闲间隙来确认。
3. **DLA 释放 GPU。** DLA 单网延迟通常不比 GPU 快，但它与 GPU 并行、功耗更低。
   Jeong 等（ACM TECS 2022）在 Jetson 上把网络拆分到 GPU+DLA 获得 101–680% 加速；我们的
   对应做法是：分类器在 DLA 上运行，同时 GPU 跑 YOLO 检测器（`--overlap`）。DLA 不支持的
   层会回退 GPU 并产生格式转换开销，导出脚本会记录每个分类器有多少层可上 DLA。
4. **共享内存的作用有限但真实。** Orin 上 `tensor.to("cuda")` 仍是一次 `cudaMemcpy`，只是
   发生在同一 DRAM 内。分类器输入 384²×3×4 B ≈ 1.77 MB、512² ≈ 3.1 MB；按 102.4 GB/s
   理论带宽估算，拷贝只有几十微秒量级，**不是瓶颈**。真正的 CPU 成本在 PIL Lanczos 缩放和
   float 转换。NVIDIA《CUDA for Tegra》应用笔记说明了 Tegra 上各类内存（可分页、pinned、
   unified）的缓存与一致性取舍；零拷贝只在 profiling 证明拷贝显著时才值得做。

## 3. 推理路径审计

每帧（`gp/models.py` → `gp/scratch_v5.py`、`gp/missing_hole.py`）：

| # | 阶段 | 当前实现 | 发现的问题 | 加速候选 | 精度风险 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 定位 | YOLO26n 640，`.pt` 或静态 FP16 engine | `.pt` 用最小矩形 letterbox（640×480 帧→640×480），静态 engine 固定 640×640，像素多 1/3，且预处理不同 | 已有 engine；可试动态 engine 保持矩形 | 预处理差异会改变框与置信度 | 已有 |
| 2 | 裁剪 | numpy 视图，4% 外扩 | 无拷贝 | — | — | — |
| 3 | 颜色转换 | 每个子系统各做一次 BGR→RGB | 每个 ROI 重复 1 次 | 共享 | 无（逐位相同） | **已实现** `--share-preprocess` |
| 4 | 分类器预处理 | PIL `fromarray`+`convert`+Lanczos 缩放+灰底填充，ToTensor/Normalize 在 CPU，`.to(device)` | 384 输入每个 ROI 生成 3 次（Scratch 2 次 + Missing Hole 1 次） | 按尺寸缓存输入张量 | 无（逐位相同，CPU 单测已验证） | **已实现** `--share-preprocess` |
| 5 | 分类器 ×4 | `.pt` FP32，逐个执行，每个之后 `.item()` 同步 | 4 次框架级调度、4 次主机同步 | TensorRT FP16 engine | FP16 数值误差 | **已实现** |
| 6 | 分类器放 DLA | — | — | DLA0/DLA1 + GPU 回退 | FP16 数值误差；回退层的转换开销 | **已实现**（可选） |
| 7 | 分类器与检测器并发 | 串行 | 分类器执行时 GPU 检测器空等 | 分类器在独立 stream/DLA 上异步，检测器同时跑 | 无（只改调度） | **已实现** `--overlap`（需 engine） |
| 8 | 检测器 ×2 | YOLO26n 960（Scratch 为 P2 头），`.pt`，Ultralytics 各自在 CPU 上 letterbox | 同一 ROI letterbox 两次；`conf_floor=0.001` 产生大量候选 | TensorRT FP16 engine | FP16 误差 + 静态 engine 的方形 letterbox | **已实现**；`--dynamic-detector` 保持矩形 letterbox |
| 9 | 检测器共享 letterbox | — | 需绕过 Ultralytics predictor | 一次 letterbox 喂两个 engine | 无 | 未实现 |
| 10 | 预处理移到 GPU | — | CPU Lanczos 成本 | GPU resize/normalize | 改变插值数值，需重新验收 | 未实现 |
| 11 | INT8 | — | — | 带校准集的 INT8（GPU 与 DLA 都支持） | 微小划痕对量化敏感 | 未实现，FP16 验收通过后再做 |
| 12 | 标注 | `frame.copy()` + 画框 | 每帧一次 0.9 MB 拷贝 | — | — | 不改 |

关于“两个分类器做 batch”：同一子系统的两个分类器是**不同网络**（EfficientNet-B0 与
ResNet18），Missing Hole 的输入尺寸也不同（512 与 384），不能放进同一个 batch 维度。
能做的是：共享相同输入（第 4 行）、在不同执行单元上并发（第 6、7 行）。真正的 batch
只适用于同一帧有多个齿轮 ROI 时对同一模型合批；当前工位通常每帧一个齿轮，暂不实现。

计时口径（读结果时要注意）：

- 分类器阶段时间**包含**其 PIL/ToTensor 预处理。开启 `--share-preprocess` 后，预处理计入
  第一个用到该尺寸的分类器。
- `--overlap` 下分类器时间 = 主机预处理 + 设备执行时间（CUDA event），与检测器时间重叠，
  所以各阶段之和会大于端到端时间。
- 端到端 `e2e_ms` 由基准脚本在 `inspect()` 外测量，结束前 `torch.cuda.synchronize()`。

## 4. 实现说明

生产路径不变：`TwoStageInspector(config)`、`AppConfig` 默认值、相机/串口/阈值/模型路径
都没有改。新增内容只在显式传参时生效：

| 文件 | 作用 |
| --- | --- |
| `gp/export_engine.py` | 新增 `python -m gp.export_engine specialists`：把六个专项模型编成 FP16 engine，可选分类器上 DLA；写 `manifest.json` 记录源 `.pt` 的 SHA256、TensorRT 版本、DLA 可放置层数。原 `export_engine.py`（定位）行为不变 |
| `gp/specialist_engines.py` | 校验 engine 清单（源权重哈希、engine 哈希、TensorRT 版本、输入尺寸），TensorRT 分类器封装（同步调用与异步 `enqueue`） |
| `gp/scratch_v5.py`、`gp/missing_hole.py` | 可选参数 `engines=`、`overlap=`；`predict(crop, shared=None)` 支持共享预处理。默认参数下行为与原来一致 |
| `gp/models.py` | `TwoStageInspector` 可选 `device=`、`engines=`、`overlap=`、`share_preprocess=` |
| `gp/power_monitor.py` | 后台采样 `tegrastats`（Jetson）或 `nvidia-smi`（独显） |
| `gp/bench.py` | `run` / `compare` / `report` 三个子命令 |
| `tests/test_jetson_bench.py` | 解析、统计、验收逻辑、engine 清单校验、共享预处理逐位一致 |

engine 只用于基准测试；要进入生产（Web 启动入口），必须先按第 6 节通过验收，再单独提交
启动参数改动。

## 5. 测量方案

### 5.1 对照组

| ID | 设备 | 定位 | 专项模型 | 选项 |
| --- | --- | --- | --- | --- |
| N0 | Orin NX | `.pt` | `.pt` | 生产基线 |
| N1 | Orin NX | FP16 engine | `.pt` | 等同当前 `run_engine.py` |
| N2 | Orin NX | FP16 engine | FP16 engine（GPU） | — |
| N3 | Orin NX | FP16 engine | FP16 engine（GPU） | `--share-preprocess` |
| N4 | Orin NX | FP16 engine | FP16 engine（GPU） | `--share-preprocess --overlap`（只靠多 stream 并发） |
| N5 | Orin NX | FP16 engine | 分类器 DLA0/DLA1，检测器 GPU | `--share-preprocess --overlap` |
| N6 | Orin NX | `.pt` | `.pt` | `--device cpu`（A78AE；可只跑 ROI 子集，次数酌减） |
| P0 | RTX 4060 Laptop | `.pt` | `.pt` | CUDA |
| P1 | 同一笔记本 | `.pt` | `.pt` | `--device cpu` |
| P2（可选） | RTX 4060 Laptop | FP16 engine | FP16 engine | 需在笔记本上自行编 engine |

N4 与 N5 的差就是 DLA 本身的贡献；N2 与 N3 的差是共享预处理的贡献。若怀疑 letterbox 差异，
加一组 N2 的 `--dynamic-detector` 版本。

### 5.2 指标定义

| 指标 | 定义 | 来源 |
| --- | --- | --- |
| 分阶段延迟 p50/p95/p99 | 定位、Scratch 分类器 1/2、检测器、融合、子系统合计；Missing Hole 同 | `InspectionResult` 字段 → `frames.csv` |
| 端到端延迟 p50/p95 | 单帧 `inspect()` 外部计时（含同步、画框） | `frames.csv: e2e_ms` |
| 每件延迟 | `--input roi` 下即每个零件的专项延迟；整帧模式下单齿轮帧的 e2e | 同上 |
| 吞吐 | 计时阶段零件数 / 墙钟时间，背靠背运行，**不含** `inference_interval` | `summary.json: timing.parts_per_s` |
| 平均功耗 | 计时窗口内 VDD_IN 平均值（W） | `tegrastats` |
| 每件能耗 | 平均功耗 × 计时时长 / 零件数（J/件） | `power.energy_per_part_j` |
| 每件动态能耗 | （运行平均功耗 − 已加载空闲平均功耗）× 时长 / 零件数 | `power.dynamic_energy_per_part_j` |
| GPU 利用率 | `GR3D_FREQ` 百分比均值 | `tegrastats` |
| DLA | 按 NVIDIA tegrastats 文档，输出可能是利用率 `X%`、频率 `Y` MHz 或 `X%@Y`（关闭时为 `off`），取决于 JetPack 版本；有百分比时记录利用率，否则只能记录活跃采样比例与频率，精确时间线用 Nsight Systems | `nvdla0_util_pct`、`nvdla0_active`、`nvdla0_mhz` |
| 内存 | `tegrastats` RAM 峰值（CPU+GPU 共用）；torch 峰值显存（不含 TensorRT 自身分配）；进程峰值 RSS | `summary.json` |
| 温度 | 各温区最大值（`tj`、`gpu`、`cpu`…） | `tegrastats` |
| 精度 | 见第 6 节 | `predictions.csv` |

功耗口径不能混用：Jetson 的 VDD_IN 是**整个模块**输入功率；`nvidia-smi` 只给**独显板卡**
功率，不含笔记本 CPU、内存和屏幕。跨设备的每件能耗比较只能并列给出并注明口径；如需系统级
对比，两台设备都接墙插功率计，读数用 `--note` 记录。`tegrastats` 采样间隔 100 ms，
只能给出 ≥60 s 窗口上的平均功耗，不能分辨单帧能耗。

### 5.3 运行规程

1. 固定功耗模式（`sudo nvpmodel -m <模式>`），脚本自动记录 `nvpmodel -q`。主结果**不**开
   `jetson_clocks`（贴近部署时的 DVFS）；如需低方差的锁频结果，单独成组，在 `--note`
   注明，不与主结果混表。
2. 停掉 GearPro Web 服务、浏览器和其他 GPU 进程；风扇策略固定；记录室温。
3. 每组：加载模型 → 预热 20 帧 → 已加载空闲 30 s（测空闲功耗）→ 计时阶段至少 60 s 且
   至少 5 遍图片集。
4. 每组重复 3 次，按 N0、N2、N5、N0、N2、N5…… 交替执行，组间冷却到起始温度附近
   （`tj` 回到 ±3 °C 内）。报告 3 次 p95 的中位数与最小–最大范围。
5. 所有组使用同一图片集、同一标签文件、同一阈值（模型包默认阈值，脚本强制，不读
   `var/settings.json`）。
6. 需要解释“为什么快”时，对 N0 与 N2 各抓一次 Nsight Systems 时间线，看 GPU 空闲间隙、
   核数量和 DLA 活动（参数以 NX 上安装的 `nsys profile --help` 为准）。

## 6. 精度验收标准（运行前冻结）

验收的是**迁移一致性**：候选组相对 `.pt` 基线（同设备 N0，或 PC 上的 P0）的判定不得变差。
下列数值是建议值，团队与导师确认后写入实验记录再开跑，跑完不得放宽。

| 检查项 | 标准 | 理由 |
| --- | --- | --- |
| 图片集与齿轮数 | 两次运行图片集相同；每张图定位出的齿轮数完全相同 | 定位差异要先单独排查，不能混进专项精度 |
| 分数偏差 | 每个子系统最大融合分数 \|Δ\| ≤ 0.02，平均 \|Δ\| ≤ 0.005 | FP16 约 3 位有效数字，经温度缩放后概率偏差应远小于阈值间隔 |
| 判定翻转 | 每个子系统及零件 OR 判定翻转数 ≤ max(1, 1% × 图片数)，且每个翻转的基线分数必须在阈值 ±0.02 内 | 只允许阈值边界上的样本翻转 |
| P_D（检出率） | 候选 TP ≥ 基线 TP（零件级、Scratch、Missing Hole 分别检查） | 不允许新增漏检 |
| P_FA（误报率） | 候选 FP ≤ 基线 FP + 1 | 最多多一个误报 |

P_D = 被判不合格的缺陷件 / 缺陷件总数；P_FA = 被判不合格的正常件 / 正常件总数。
`compare` 同时给出 Wilson 95% 区间，提醒样本量小（150 张中缺陷件只有几十个）。

数据使用：

- 开发阶段在**非锁定**数据（验证集或回放包）上反复跑。
- 最终只在锁定的 150 张独立测试集上跑**一次**做迁移回归；`docs/missing-hole-v1.md` 已规定
  锁定 test 只能用于迁移回归，不能用于调阈值。
- 如锁定测试集是 ROI 图（专项指标在 ROI 上计算），用 `--input roi`；整帧数据再用
  `--input frame` 单独衡量定位 engine 的影响。

精度通过后，候选才算“有效加速”需满足其一（建议值，同样在运行前冻结）：3 次重复的
端到端 p95 中位数比 N0 降低 ≥15%；或每件能耗降低 ≥15% 且 p95 不恶化超过 5%。
3 次重复中不得出现 OOM、热降频或 p99 长尾失控（p99 > 2 × p50）。

未通过时：先用 `--dynamic-detector` 排除 letterbox 差异；仍不通过的模型保留 `.pt`，
不得改阈值迁就 engine。

## 7. NX 操作步骤

```bash
cd /home/jetson/Projects/Machine_vision
git lfs pull                                  # Missing Hole 权重是 LFS 文件
python3 -c "import tensorrt; print(tensorrt.__version__)"
pip install onnx                              # 仅当分类器导出报缺少 onnx 时

# 1) 编 engine（只需在换权重或升级 JetPack 后重做）
python -m gp.export_engine locator                                   # .cache/exports/model1.engine
python -m gp.export_engine specialists                               # .cache/exports/specialists/fp16/
python -m gp.export_engine specialists --classifier-dla 0,1          # .cache/exports/specialists/fp16-dla/
cat .cache/exports/specialists/fp16-dla/*/manifest.json              # 查看 dla_layers：可上 DLA 的层数

# 2) 标签文件：image,scratch,missing_hole（相对 --images 的路径；1/0/空）
IMG=/path/to/images; LBL=/path/to/labels.csv; ENG=.cache/exports/specialists
COMMON="--images $IMG --labels $LBL --input roi"

python -m gp.bench run $COMMON --tag N0-pt                 --out var/bench/N0-r1
python -m gp.bench run $COMMON --tag N2-trt  --locator .cache/exports/model1.engine --engines $ENG/fp16     --out var/bench/N2-r1
python -m gp.bench run $COMMON --tag N3-trt-share --locator .cache/exports/model1.engine --engines $ENG/fp16 --share-preprocess --out var/bench/N3-r1
python -m gp.bench run $COMMON --tag N4-trt-overlap --locator .cache/exports/model1.engine --engines $ENG/fp16 --share-preprocess --overlap --out var/bench/N4-r1
python -m gp.bench run $COMMON --tag N5-dla  --locator .cache/exports/model1.engine --engines $ENG/fp16-dla --share-preprocess --overlap --out var/bench/N5-r1
python -m gp.bench run $COMMON --tag N6-cpu  --device cpu --passes 1 --min-seconds 0 --out var/bench/N6-r1

# 3) 精度验收（退出码 0 = 通过）与汇总表
python -m gp.bench compare var/bench/N0-r1 var/bench/N2-r1 --out var/bench/N2-r1/compare.json
python -m gp.bench report var/bench/*-r1
```

PC（RTX 4060 Laptop）上同样命令，去掉 `--locator/--engines` 即为 P0；加 `--device cpu` 为 P1。
功耗自动用 `nvidia-smi`。`--input roi` 下定位不参与，定位 engine 的效果要用整帧数据
（`--input frame`）另测。

输出在 `var/bench/<run>/`（不提交）：`summary.json`（环境、git 提交、模型与 engine 哈希、
统计结果）、`frames.csv`、`predictions.csv`、`power.csv`，以及原始 `tegrastats.log` 或
`nvidia-smi.log`（字段格式与预期不同时可重新解析）。

## 8. 结果记录表（实测后填写，禁止填入估计值）

| ID | e2e p50 / p95 (ms) | 定位 p95 | Scratch p95 | Missing Hole p95 | 件/s | 平均功耗 W（口径） | J/件 | 动态 J/件 | GPU % | 峰值温度 °C | 精度验收 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| N0 | | | | | | | | | | | 基线 |
| N2 | | | | | | | | | | | |
| N3 | | | | | | | | | | | |
| N4 | | | | | | | | | | | |
| N5 | | | | | | | | | | | |
| N6 | | | | | | | | | | | |
| P0 | | | | | | | | | | | |
| P1 | | | | | | | | | | | |

`python -m gp.bench report` 直接输出前几列。

## 9. 参考文献

题名与完整作者请按 DOI 在正式报告中补全。

- Jeong et al. *ACM Transactions on Embedded Computing Systems*, 2022. DOI: 10.1145/3508391。
  Jetson 上 GPU+DLA 拆分推理，101–680% 加速。
- Mittal. *Journal of Systems Architecture*, 2019. DOI: 10.1016/j.sysarc.2019.01.011。
  Jetson 平台深度学习优化实现综述。
- Molleda et al. *Journal of Real-Time Image Processing*, 2026. DOI: 10.1007/s11554-026-01974-1。
  YOLOv26 在 Jetson Orin 上的 TensorRT FP16 部署。
- NVIDIA. CUDA for Tegra（应用笔记）：Tegra 上 CPU/iGPU 共享内存的分配类型与缓存一致性。
  https://docs.nvidia.com/cuda/cuda-for-tegra-appnote/
