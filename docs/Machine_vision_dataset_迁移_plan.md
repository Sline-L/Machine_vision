# Machine_vision_dataset → Machine_vision 迁移 Plan

日期：2026-09-15

状态：本地迁移与验证已完成；尚未合并、推送或在 Jetson 上部署。

## 实施结果（2026-09-15）

- `migration/dataset-missing-hole-v1` 已同步源提交 `dca0306` 的 49,531 个跟踪文件，并增加本 plan；快照提交为 `734e0eb`，可移植性提交为 `6f28a41`。
- `feat/missing-hole-v1-web` 已集成 Missing Hole V1、双专项 OR 判定、独立阈值、API v2/v1 兼容、SystemSnapshot v2 和新版 Web 页面；实现提交为 `29640d9`、`a5153d4`、`fb43752`、`de608d9`。
- 三份新增生产权重使用 Git LFS，两个工作树的 `git lfs fsck` 均通过。应用端 41 项测试、Python 编译、依赖一致性、JSON 与前端构建均通过。
- Scratch V5 和 Missing Hole V1 的源实现与生产运行时在固定样本上的三路概率及融合概率逐值一致；完整 Model1 → 双专项 CPU 链路成功输出 1 个齿轮和 `missing_hole` 拒绝原因。
- 远端 fetch 因当前环境缺少 GitHub SSH 私钥未完成，因此以上基于调查时已有的本地引用。Jetson CUDA、显存、相机和串口验收仍按第 6、7 节执行。

目标：将最新研究成果完整更新到 `dataset` 分支，并将 Scratch V5 + Missing Hole V1 双专项能力集成到 `main-web`。

## 1. 推荐方案

采用两条独立交付线：

1. **研究资料线**：以 `Machine_vision_dataset` 的固定提交为源，将数据、训练脚本、实验记录、最终模型和评估档案同步至 `Machine_vision:dataset`，保留源目录结构与 Git LFS 规则。
2. **应用集成线**：从 `Machine_vision:main-web` 创建功能分支，复用已有 Model1、Scratch V5 和 Web 框架，新增 Missing Hole V1 常驻运行时，逐 ROI 执行两个专项的 OR 判定。

两条线通过模型发布清单关联。不要把整个 `dataset` 分支 merge 到 `main-web`，也不要将研究仓库覆盖到应用根目录。两分支没有共同祖先，承担的职责也不同。

第一阶段交付保持现有模型、温度、输入尺寸和阈值；TensorRT、分类器门控、模型蒸馏、多视角及重新训练放在后续任务。当前专项 OR 是可运行基线，其盲测指标仍未达到 Recall ≥ 0.95 / FPR ≤ 0.20。

## 2. 本次调查基线

### 2.1 分支与工作区

| 对象 | 本地提交 | 实际内容 / 状态 |
| --- | --- | --- |
| `Machine_vision_dataset:main` | `dca0306` | 最新本地研究快照，工作区干净 |
| `Machine_vision:dataset` | `581647d` | 当前检出分支，早期研究资料快照；`runs/`、`outputs/` 被忽略 |
| `Machine_vision:main-web` | `1b54d74` | FastAPI + Vue 3 应用，已集成 Model1 + Scratch V5 |

这些本地分支与各自本地 `origin/*` 引用一致；本次没有 fetch，不能据此断言远端没有更新。实施前应重新获取远端引用，若提交变化，重算清单与差异。

`Machine_vision` 当前还有未跟踪的 `final/`、`web/`。不要在该工作目录直接 checkout、清理或覆盖；实施时使用独立 worktree。`main-web` 中的 `AGENTS.md` 要求保留无界面架构、硬件默认值、内置 Ultralytics 和现有模型，并按提交约定完成检查与提交。

### 2.2 项目和目录职责

| 位置 | 内容 | 迁移定位 |
| --- | --- | --- |
| 研究仓库 `dataset_gear/` | 第一阶段齿轮定位原图、VOC XML、YOLO 标签 | 数据归档，供 Model1 复现 |
| `dataset_defects/images/`、`annotations/` | 原始/专项数据，含 `*_scratch`、`*_missing_tooth` | 标注和拆分的源数据 |
| `dataset_defects/scratch_v5/` | V5 派生分类/检测数据、manifest、预检 | 保留拆分及防泄漏证据 |
| `dataset_defects/missing_hole_v1/` | Missing Hole 拆分、六套标签及预检 | 保留 difficult 策略与分组 |
| `dataset_defects/auto_search_*`、`binary_defect_v4/` 等 | 历史派生数据 | 随研究线保留，不进入应用部署 |
| `runs/` | 所有训练候选、权重与训练过程 | 复现和追溯，不作为生产默认路径 |
| `outputs/` | 最终权重、推理配置、排行榜、测试报告和可视化 | 研究线完整保留；应用线按白名单取产物 |
| `docs/`、`archive/` | 当前说明、历史代码与报告 | 保留；旧报告中的历史路径不批量重写 |
| `main-web:gp/` | 配置、常驻线程、推理、统计、串口、API | 本次应用集成主体 |
| `main-web:web/`、`gp/static/` | Vue 源码和已构建页面 | 修改源码后同步构建产物 |
| `main-web:model/` | Model1 和可部署 Scratch V5 包 | 增加 Missing Hole 独立模型包 |
| `main-web:ultralytics/` | 内置 Ultralytics 源码 | 保留，先验证兼容性 |

研究仓库根 README 仍混有“当前 V4”“下一轮命名 V5”等历史段落。当前模型选择应以 V5 迁移说明、Missing Hole 最终报告、总实验报告和最终配置为准，不仅依赖根 README。

### 2.3 已核实的差异

按两个提交的 Git 树比较：源有 **49,531** 个跟踪文件，目标 `dataset` 有 **33,001** 个；新增 **16,530** 个，无源端删除项。

主要新增：

- `dataset_defects/`：13,964 个文件。
- `outputs/`：1,047 个文件；`runs/`：1,458 个文件。
- `docs/`：51 个文件，包括 Missing Hole 实验报告及总流程报告。
- Missing Hole 准备、训练、评估、运行时，双专项 CLI、统一模型训练、测试和 GPU 监控脚本。
- `.gitattributes`、`LICENSE`。

Git blob 显示的 19,199 个修改中，**19,196 个在 LFS 实体内容还原后与旧版本完全一致**；真正修改的既有文件只有 `.gitignore`、`README.md`、`docs/README.md`。因此不要将大量图片/权重的 blob 变化解释成重新标注或重新训练。

源 `.gitattributes` 对模型及图片使用 LFS；本次扫描没有缺失的跟踪文件，也没有未下载的 LFS 指针占位文件。本地已安装 Git LFS。迁移后仍需在目标远端做全新克隆验证，不能因为本地能运行就认为对象已上传。

源目录当前磁盘占用约：`dataset_defects/` 670 MB、`dataset_gear/` 332 MB、`outputs/` 438 MB、`runs/` 2.3 GB，另有 `.git/` 2.7 GB。这是本地占用，不等于 LFS 去重后的上传量；`.git/` 不作为文件同步内容。

## 3. 模型基线与业务语义

### 3.1 固定推理协议

| 项目 | Scratch V5 | Missing Hole V1 |
| --- | --- | --- |
| 分类器 1 | EfficientNet-B0，384，温度 0.7 | EfficientNet-B0，512，温度约 1.0 |
| 分类器 2 | ResNet18，384，温度 2.05 | ResNet18，384，温度 2.375 |
| 检测器 | YOLO26-P2，960，温度 2.125 | standard YOLO26n 单类，960，温度约 1.85 |
| TTA | none | none |
| 融合 | 0.25 × 分类器均值 + 0.75 × 检测概率 | 0.5 × 分类器均值 + 0.5 × 检测概率 |
| 默认阈值 | `0.300273610279458` | `0.3413327979078584` |
| 检测输入参数 | conf=0.001，IoU=0.7 | conf=0.001，IoU=0.7 |

温度值在生产配置中保留源 JSON 的完整精度。分类器预处理统一遵循源实现：RGB、保持比例的 LANCZOS 缩放、居中灰色 `(238,238,238)` 填充、ImageNet 标准化；校准为 `sigmoid(logit(clamp(p, 1e-6, 1-1e-6)) / T)`。

```text
scratch_reject = scratch_probability >= scratch_threshold
missing_hole_reject = missing_hole_probability >= missing_hole_threshold
roi_reject = scratch_reject OR missing_hole_reject
frame_reject = 任一有效齿轮 ROI 的 roi_reject
```

两个专项的概率不能直接求均值或取最大后与旧单阈值比较：阈值不同，这会改变判定。也不构造未经校准的“任意缺陷概率”。检测框仅辅助复核，是否有框不能代替图像级判定。

源文件夹继续使用 `missing_tooth`，新运行时/API 语义使用 `missing_hole`，中文显示“缺齿/缺口”。`bottom/oblique/side` 是实验监督和诊断标签，最终生产检测器为单类，不能承诺输出可靠的位置分类。

### 3.2 已记录的测试结果

| 基线 | 测试口径 | Recall | FPR | TP/FP/TN/FN |
| --- | --- | ---: | ---: | --- |
| Scratch V5 | 150 张，31 张 scratch，119 张无 scratch | 0.8065 | 0.1681 | 25/20/99/6 |
| Missing Hole V1 | 150 张，44 张 missing_hole，106 张无该缺陷 | 0.8182 | 0.0377 | 36/4/102/8 |
| 双专项 OR | 150 张，71 张任意缺陷，79 张正常 | 0.8873 | 0.2278 | 63/18/61/8 |
| 统一单模型 | 相同任意缺陷口径 | 0.7606 | 0.4177 | 54/33/46/17 |

双专项测试有 4 张同时具有两类缺陷。各行负样本定义不同，不能将专项 FPR 直接与任意缺陷 FPR 作同口径比较。Missing Hole 的 oblique Recall 为 0.5882，是已知弱点。

以上是源报告记录，本次未运行模型重新测量；它们也不代表主项目“相机原帧 → Model1 裁剪 → 双专项”的端到端成绩。

## 4. 研究资料线：更新 dataset 分支

### D0：固定输入和隔离工作区

- [ ] 获取远端最新引用，记录源 commit、目标两分支 commit、干净状态。
- [ ] 从 `dataset` 创建 `migration/dataset-missing-hole-v1` 独立 worktree；另从 `main-web` 创建 `feat/missing-hole-v1-web` worktree。
- [ ] 生成源跟踪文件 manifest：相对路径、实体大小、SHA256、LFS oid（如有）、源提交。
- [ ] 保存旧目标分支引用；清单记录目标原有文件。保留当前工作区的 `final/`、`web/`。

### D1：按源跟踪清单同步完整研究快照

同步源提交跟踪的全部研究内容，并保留目录布局。排除 `.git/`、虚拟环境、缓存、机器本地配置及未跟踪临时文件。不要依赖 `cp -r` 或 `rsync --delete` 对整个仓库做无差别覆盖。

先在目标集成分支配置 Git LFS 规则，再导入实体文件。目标原先忽略 `runs/`、`outputs/`，应采用源研究分支的忽略策略，保证这两个目录确实进入索引。

源 `.gitattributes` 生效后，对对应图片/模型执行受控 renormalize，使当前快照使用 LFS 指针；旧提交中已有的大文件暂不重写历史。不执行 `git lfs migrate import --everything` 或强推。源 `LICENSE` 随研究资料保存，不覆盖应用分支的 `LICENSE.md`。

本次原始差异没有删除项；同步应保留目标专属文档（包括本 plan）。未来遇到源端删除，先列入删除清单再处理，不能推导为目标所有额外文件均应删除。

### D2：区分快照可追溯与脚本可运行

完整复制后，部分配置仍有 Windows `F:\Work\VSCode\Projects\DATASET\...` 绝对路径；`train_scratch_v5.py` 的 `P2_YAML` 还指向 `.venv/Lib/site-packages/...`。仅搬文件不等于在 Linux 可复现。

- 先提交忠实源快照，再以单独提交处理可移植性，避免混淆来源差异。
- 活跃推理配置支持相对配置目录解析权重；保留原始配置的副本或哈希，输出转换清单。
- 数据 YAML、manifest 和训练脚本逐项区分“执行时要读取的路径”和“历史记录路径”；只转换前者，历史报告原样保留。
- `P2_YAML` 根据实际 Ultralytics 安装/源码位置解析，不依赖 Windows 虚拟环境目录。
- 原始标注、group、train/val/test 分配及锁定评估文件不重生成、不覆盖。

### D3：研究线验收

- [ ] 对同步白名单逐文件比对实体 SHA256；LFS 指针变化单独统计。
- [ ] 检查 `git lfs ls-files` / `git lfs fsck`，推送后用全新克隆及 `git lfs pull` 验证目标远端对象完整。
- [ ] 预检统计保持：训练池 496、test 150、框 614/168、派生 train/val 397/99。
- [ ] 跑 `tests/test_missing_hole_v1.py`；它有 Torch/Ultralytics 导入依赖，且依赖派生数据，不能当成无依赖应用单测。
- [ ] 核对六套标签、仅 difficult 的 6 张训练图排除逻辑、group 不跨集合。
- [ ] 保留 Scratch 测试报告及 Missing Hole 的 `evaluation_lock.json`、`raw_predictions.json`、测试报告和逐图预测。
- [ ] 数据同步提交和可移植性提交分别通过差异审阅，随后合入 `dataset`。

## 5. 应用集成线：更新 main-web

### W1：最小生产资产

本次实际计算 SHA256 确认：源 Model1 与 `main-web:model/model1.pt` 完全一致；源 V5 三权重也与 `main-web:model/model2/` 完全一致。保留这些现有文件及已适配的 V5 配置，无须重新覆盖。

建议新增：

```text
model/missing_hole_v1/
  inference_config.json           # 由源配置显式转换，包含相对路径及 SHA256
  classifier_1.pt
  classifier_2.pt
  detector_3.pt                   # 保留源文件名
  manifest.json                  # 源提交、源/转换后配置哈希、三权重哈希
gp/missing_hole.py                # 独立常驻推理运行时
gp/defects.py                     # 双专项结果与 OR 编排
tests/test_missing_hole_runtime.py
tests/test_defect_pipeline.py
docs/missing-hole-v1.md
```

实际权重基线：

| 资产 | 字节数 | SHA256 |
| --- | ---: | --- |
| Model1 `best.pt` → 已有 `model1.pt` | 20,740,933 | `d79912510810fdfe1b0fb6d4080e669dc14acad0cdb37db9c851f2b1fe7371f2` |
| Scratch `classifier_1.pt` | 16,314,725 | `44461f4e03ff716266a3123bf1ba4611a1c965cf8776d0e523f128cf7c0b8438` |
| Scratch `classifier_2.pt` | 44,780,619 | `d07678a6da421c4edc00ac24b8c5052b0b8b7f8b1614b9d82563ecefbf59360d` |
| Scratch `detector.pt` | 5,902,651 | `4451e3f3664e3ad551926dc771e8cf4d0da9cd6648a9b841ea9d22bea86f15b3` |
| Missing Hole `classifier_1.pt` | 16,314,725 | `98a89cb0eea938b290f7cd2d6fa847634cef666aceca49e4082a729b76353228` |
| Missing Hole `classifier_2.pt` | 44,780,619 | `65db4aa1eeee41ab96b38bb860ef017994511472ee1f68cae214b0ee604a66e1` |
| Missing Hole `detector_3.pt` | 5,377,541 | `b4b7870e07e63a548be735278652025ac4ec67ae771a7ed771d55e5122b58b63` |

应用线仅新增必要模型资产及发布说明，不复制训练数据、全部 runs、统一模型、虚拟环境或整个研究 `final/`。如果为应用线新增 LFS 规则，先限定新增模型包路径，避免顺带将内置样例图片和旧资产全部重新归一化。

### W2：适配配置与运行时

`main-web:gp/scratch_v5.py` 已完成相对路径、哈希校验、一次加载、预热和训练解耦，不能用研究版 `infer_scratch_v5.py` 覆盖。

Missing Hole 的源格式是 `models[]`，而已有 V5 格式是 `classifiers[] + detector`，且加载器强制 `version=scratch_v5`、检测类别为 `scratch`。**不能只替换配置和三份权重。**

建议保留 Missing Hole 的 `models[]` 格式，用专用加载器校验并解析；显式补充源代码固定的 `conf_floor=0.001`、`iou=0.7`、权重 SHA256。校验模型名称引用、kind/family、输入尺寸、温度、fusion、阈值和单类语义。

运行时参考 `missing_hole_runtime.py` 的数值路径，但改为接收 OpenCV BGR ROI，转换 RGB 后执行分类，检测器接收一致的 BGR 图像。三个模型常驻一个设备，初始化时加载/预热，调用时只推理。

源 `missing_hole_runtime.py` 从 `train_scratch_v5.py` 导入函数，并按模型遍历整个图片集后释放资源；`infer_gear_defects.py` 是批量 CLI。二者用于一致性参考，不在每帧请求中启动，也不直接导入生产进程。仅复用必要的预处理、checkpoint 构造、校准和融合函数；若提取公共 helper，先锁定 V5 回归结果。

自定义分类器按 checkpoint 架构加载，不能传给 `YOLO()`；构造时不下载 ImageNet 权重。最终包仅支持已经验收的 TTA/融合组合，遇到其他模式显式报错。

### W3：贯通判定、状态和串口

| 文件 | 需要修改的行为 |
| --- | --- |
| `gp/models.py` | 同一 Model1 ROI（现有 4% margin）送两个专项；两个辅助框分别回映到原帧；按明确 OR 结果着色 |
| `gp/types.py` | 每个 observation 增加两专项结果及明确 `decision`/`is_defective`；`InspectionResult.is_defective` 不再只比较旧分数 |
| `gp/config.py` | 新增 Missing Hole 配置路径及独立阈值；处理已有 settings 的版本迁移和校验 |
| `gp/runtime.py` | 序列化专项结果和耗时；计数、串口统一消费同一次推理产生的最终判定 |
| `gp/worker.py` | 模型加载和故障状态覆盖整个双专项；任一必要模型失败则暂停并报告错误 |
| `gp/telemetry.py` | 分别报告两专项、总推理耗时、加载状态及错误；同步快照 schema/示例 |
| `gp/profiles.py` | FULL/SPARSE 均执行完整双专项；SPARSE 只降低推理频率；SAFE_STOP 继续停止检测 |
| `gp/web.py`、`web/src/App.vue` | 输出和显示双概率、双阈值及命中原因；同步设置验证和 API 版本 |

建议 observation 新字段采用 `specialists.scratch`、`specialists.missing_hole`，各含 probability、threshold、reject、classifier_probability、detector_probability、auxiliary_box、latency_ms；顶层 decision 为最终 OR。保存本次推理实际使用的阈值，避免用户修改设置后旧结果被重新判定。

迁移策略：旧 `defect_threshold` 仅映射为 scratch 阈值；Missing Hole 默认取自身配置。新旧 scratch 字段同时出现且冲突时拒绝请求，不静默覆盖。备份并原子更新 `var/settings.json`，保留操作员已有 scratch 阈值并明确显示是否偏离发布默认值；基准验收使用锁定默认值。

旧 `defect_score` 如保留，只作为 scratch_probability 的兼容别名，不能继续作为总缺陷概率或最终判定依据。面向新 UI 的结果协议建议升至 `api.v2`，同步 API 文档和测试；旧客户端升级或获得显式版本不兼容提示，不能继续无提示显示旧语义。EdgeMedic 的快照版本也须按字段变化明确演进，不能继续把双专项总耗时伪装成 `scratch_v5` 耗时。

正常有效结果继续串口 ASCII `01`，不合格结果继续 `02`。无齿轮不增加计数、不发送合格；解码失败、空 ROI、NaN/Inf、权重缺失、OOM 等走错误/停止路径，不自动降级为 scratch-only 后输出合格。

当前统计依赖帧结果和冷却时间，不是目标跟踪后的逐齿轮唯一计数。首版保持该机制；两专项同时命中不能计两次或发送两次串口消息。生产单齿轮 ROI 与多齿轮画面均需要验收。

### W4：Web 与文档

- 保持当前中文单屏仪表盘，显示“划痕概率 / 缺齿缺口概率 / 最终判定 / 命中原因”。
- 设置页将旧“缺陷阈值”明确改为“划痕阈值”，新增独立“缺齿/缺口阈值”。
- 记录 Scratch、Missing Hole 与 Model1 版本，显示两专项耗时；健康页能区分哪一支失败。
- 更新 README、`docs/architecture.md`、`docs/web-api.md`、`docs/scratch-v5.md`、`docs/model-formats.md`、文档索引及相关遥测 schema。
- 重建并提交 `gp/static/`，保留登录、控制租约、视频模式禁串口等既有行为。

## 6. 验收设计

### A. 不依赖硬件的逻辑回归

- OR 真值表四种组合、分数恰等于阈值、两支阈值不同、两支同时命中、无齿轮、多 ROI。
- 空图/损坏图、非法配置、哈希不符、LFS 占位文件、NaN/Inf、模型部分加载失败。
- ROI 的 BGR/RGB、比例填充、辅助框坐标回映；辅助框缺失不改变判定。
- 设置迁移、重复/冲突阈值、重启持久化、推理结果阈值快照。
- 最终判定 → UI → 统计 → 串口一致；视频模式不发送串口，错误不能累计 good。
- FULL/SPARSE 均调用两专项，SAFE_STOP 停止；原有控制锁、认证、视频上传和遥测测试通过。

应用分支按仓库要求执行：

```bash
python -m py_compile gp_main.py run_pt.py run_engine.py export_engine.py gp/*.py
python -m unittest discover -s tests -v
python -m pip check
```

在 `web/` 中执行 `npm ci`、`npm run build`；运行 `git diff --check`。本 plan 编写阶段只做文档检查，不将这些未来验收描述为已通过。

### B. 同一输入的模型迁移一致性

1. 固定源配置、权重、输入实体哈希和运行环境，先生成参考输出；所有重跑产物写新目录，不覆盖锁定档案。
2. 同一张图片分别传给源推理实现及新运行时，比较各分支校准概率、融合概率、阈值和 decision。此步骤不引入 Model1 重新裁剪。
3. V5 使用历史 `val_001.jpg`（PASS，约 0.0693）、`val_017.jpg`（REJECT，约 0.7392）；Missing Hole 可复核报告已使用的 `test_001`、`test_009`，并记录完整相对路径以避免同名误取。
4. 增加正常、scratch-only、missing-only、双缺陷及临界样本；以文件哈希识别，不能只按 stem 将两专项标签拼接。
5. 同版本/设备优先要求概率绝对误差 ≤ `1e-5`，decision 完全一致。主项目 V5 文档已记录跨版本约 `2.3e-5` / `4.1e-4` 的偏差；超过阈值时先排查实现和依赖，跨环境另立有依据的容差，不能仅为通过验收放宽。
6. 锁定测试仅做回归一致性，不调阈值；期望恢复第 3.2 节混淆矩阵。若阈值附近结果翻转，应记录并解决或明确阻断发布，而非只看总 Recall 接近。

### C. 真实 ROI 与 Jetson 联调

源 CLI 直接读图片，主项目先经 Model1 加 4% margin 裁剪，两者输入分布可能不同。完成 B 后，另用新采集/已授权的回放视频验证真实 ROI，单独报告端到端指标；不能要求裁剪后直接复现原图混淆矩阵，也不能用旧 test 调整 margin。

源文档记录训练环境为 Python 3.13.12、Torch 2.14.0+cu130、torchvision 0.29.0+cu130、Ultralytics 8.4.142；主项目内置 Ultralytics 标记为 **8.4.13**，requirements 仅有 Torch/torchvision 下界。本次未核验目标板实际环境。

实施时记录实际 Python、Torch、torchvision、CUDA、JetPack、TensorRT、GPU 及 `ultralytics.__file__`，先验证当前内置代码能加载新检测器；安装 pip 包不一定替换仓库内置导入。若不兼容，单独安排最小兼容修复或版本升级，不直接覆盖整个源码树。

Model1 加双专项共 **7 个模型实例**。磁盘权重约 130 MB 不等于显存占用；源训练监控峰值也不能代表七模型常驻峰值。

- 记录预热时间、单/多 ROI 的 p50/p95 延迟、真实推理吞吐、峰值显存/内存、温度、长时间运行及 OOM 恢复。
- 继续使用一个推理 worker 串行运行两个专项；相机和推理不进入 FastAPI event loop，不在多个 Web worker 中重复加载模型。
- 页面流 10 FPS、`inference_interval=0.10` 都不是双专项推理达到 10 FPS 的证明。上线门槛须结合传送带速度和剔除窗口确定，未有现场预算前不宣称实时性达标。
- 首版使用 `.pt` 完成一致性。Model1 已有 `.engine` 部署可另行回归；新专项 TensorRT/INT8 不纳入首轮迁移。
- 保留物理相机、串口、冷却计数、定量/定时停止和多终端操作的实机联调记录。

## 7. 交付顺序与回滚

| 顺序 | 交付件 | 完成条件 |
| --- | --- | --- |
| 1 | 源/目标清单、分支基线、LFS 盘点 | 来源固定，路径/实体哈希可追溯 |
| 2 | dataset 快照及独立可移植性提交 | D3 通过，目标端完整克隆可取回资产 |
| 3 | Missing Hole 模型包与运行时 | 配置验证、单支参考一致性通过 |
| 4 | 双专项结果协议与 Web/串口集成 | A 通过，前后端和遥测版本一致 |
| 5 | 模型回归及目标板报告 | B、C 完成，明确精度和延迟限制 |
| 6 | 合入 main-web 的可部署版本 | 保存旧版本、模型 manifest、配置备份，具备回滚路径 |

建议按 `data(dataset)`、`fix(dataset)`、`feat(inference)`、`feat(web)`、`test(inference)`、`docs(deployment)` 拆分可审阅提交。应用线无需等待全部历史训练产物的网络上传才开始开发，但发布前要有对应的稳定研究提交和模型 manifest。

回滚必须同时恢复应用代码、静态页面、模型发布清单和 settings 备份。保留旧 Scratch-only 发布版本作为显式回滚目标；回滚后 UI 和记录明确标识仅支持划痕，不能继续显示双专项已启用。禁止通过缺文件后的静默降级实现回滚。

数据线通过旧分支引用/新修复提交恢复，保留已发布历史；不使用强推或清空研究目录。模型、配置、前端分批替换可能产生不一致，应以完整发布目录切换并重启服务。

## 8. 实施前需要补齐的信息

这些事项不阻塞文档或本地运行时开发，但影响最终部署验收：

1. 目标 Jetson/工控机的实际软件环境，以及当前部署是否已切到 `main-web`（分支说明中的 NX 记录仍指向 `srtp`）。
2. 现场允许的最大检测延迟、并发 ROI 数和剔除窗口。
3. 目标 Git/LFS 服务的空间、传输限额及凭据；完整研究快照包含历史候选，需按 manifest 估算上传量。
4. 是否有消费旧 API/EdgeMedic 快照的外部客户端，安排 `api.v2` 升级顺序。

本方案默认先完整更新 `dataset`，再交付双专项 Web 版本；目标设备和性能预算未确定时，完成本地集成及回放验收，保留实机验收为发布门槛。

## 9. 依据

研究仓库：

- `README.md`、`docs/README.md`
- `docs/Scratch_V5_迁移与集成说明.md`
- `docs/missing_hole_v1/README.md`、`FINAL_REPORT.md`
- `docs/V3_V4_V5_MissingHoleV1_总实验流程报告.md`
- 两专项 `inference_config.json`、Missing Hole `test/test_report.json`
- `infer_gear_defects.py`、`missing_hole_runtime.py`、`train_scratch_v5.py`、数据准备/评估脚本与测试

应用仓库 `main-web` 分支：

- `AGENTS.md`、`README.md`、`docs/scratch-v5.md`、`docs/model-formats.md`
- `gp/models.py`、`gp/scratch_v5.py`、`gp/types.py`、`gp/config.py`
- `gp/runtime.py`、`gp/worker.py`、`gp/telemetry.py`、`gp/profiles.py`、`gp/web.py`
- `web/src/App.vue`、`model/model2/inference_config.json`、`requirements.txt`、`ultralytics/__init__.py`

调查采用本地 Git 分支内容、文件清单与实体哈希。本次仅编写迁移方案，没有修改模型、训练数据、应用代码或分支指向。
