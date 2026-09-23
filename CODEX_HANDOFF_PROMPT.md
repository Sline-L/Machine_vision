# GearPro / SRTP 接手 Prompt（交给另一台电脑上的 Codex）

你现在要正式接手 GearPro / SRTP 项目。此前大量代码和文档由 Cursor 辅助开发，但不要默认既有实现正确，也不要为了“延续进度”继续堆功能。你的职责是先核实事实、保护研究证据和 Git 历史，再把项目收敛到真正可验收的工程与研究主线。

## 一、项目与仓库

- GitHub：`https://github.com/Sline-L/Machine_vision`
- 技术栈：Python、FastAPI、Vue 3、OpenCV、串口、YOLO/TensorRT、Jetson Orin NX 16GB。
- 项目目标：构建齿轮工业缺陷检测闭环，包括相机与机械采集、齿轮定位、划痕与缺齿缺口双专项、多视角/几何处理、Jetson 边缘推理、STM32/串口分拣、Web UI、日志与受限 Agent。
- 开始任何工作前完整阅读仓库根目录 `AGENTS.md` 和 `COMMIT_CONVENTION.md`，并服从其中的项目约束。
- 不添加 ROS、LiDAR、PX4；不把 Qt 重新引入 headless Web 运行时；不擅自改硬件默认参数；不删除模型、历史实验或 vendored `ultralytics/`。

## 二、Git 事实与分支角色

不要默认 `main` 是最新实现。先执行只读检查：

```bash
git status --short --branch
git remote -v
git fetch origin --prune
git branch -a -vv
git log --oneline --decorate -10
```

关键分支：

- `main@2d19aea`：公共重构基线，但不是最新 Agent 集成线。
- `main-web@de608d9`：当前双专项 Web/视觉应用基线。
- `dataset@9dfcc71`：视觉数据、训练实验、Missing Hole 报告与研究基线。
- `integration/dual-specialist-edgemedic@ed9b525`：截至交接文档核实的最新双专项 + EdgeMedic 集成基线，是继续 Agent 工作的正确源码起点。
- `srtp-agent/v2-pressure-pilot@fe2006e1`：4B/A3 历史研究、压力实验及中期证据线；应冻结参考，不直接继续堆功能。
- `experiment/v3-1-holdout-adjudication@36736d8f`：研究冻结与 holdout 裁决线；不可重写历史或擅自打开 fresh holdout。
- `feature/multiview-polar-unwrapping`：视觉新工作线，目前从 `main-web` 起步。
- `feature/agent-v3`：远端目前仅指向 `main-web@de608d9`，尚无有效 Agent 新提交，因此基线不正确。不要在这个错误基线上盲目开发。先取得用户同意/确认远端状态，再将 Agent v3 工作线改为从 `integration/dual-specialist-edgemedic@ed9b525` 起步；禁止误删他人新提交或未经核对强推。
- `local-workspace@555a30f`：原电脑本地保存的 SRTP 计划与素材，不一定存在于远端，不得假定另一台电脑能取得。

只抓取工作所需分支，不要无目的拉取全部历史。仓库历史约 650 MiB，已有模型使用 Git LFS；新增权重、数据集、TensorRT Engine 不得直接塞进普通 Git 历史。

## 三、视觉系统的真实状态

当前视觉主链路：

```text
相机帧
→ Model1 定位整颗齿轮
→ ROI 四周外扩约 4%
→ Scratch V5（三路融合）
→ Missing Hole V1（三路融合）
→ 两专项独立阈值
→ OR 判废
→ UI / 统计 / 串口
```

报告中的锁定测试结果：

- Scratch V5：Recall `0.8065`，FPR `0.1681`。
- Missing Hole V1：Recall `0.8182`，FPR `0.0377`。
- 双专项 OR：Recall `0.8873`，FPR `0.2278`。
- 当前目标 `Recall >= 0.95` 且 `FPR <= 0.20` 尚未达到。
- Missing Hole 的 oblique 子组 Recall 约 `0.5882`，这是明确短板。

不要继续无差别堆分辨率、epoch 或网络结构。已有证据表明主要问题是成像信息不足、斜视缺口、低对比划痕、侧齿高光和真实负样本不足。

视觉主线优先级：

1. 机械定位、光照和成像可见性。
2. 多视角采集；同一实体齿轮的全部视角必须按同一 group 管理。
3. 工件 ID 与跨帧/跨视角关联，取代单纯“帧结果 + 5 秒冷却”。
4. 齿轮中心、内外圆和尺度归一化。
5. 齿圈极坐标展开为矩形纹理，进行单变量对照实验。
6. 新批次一次性 blind test 和真实高光负样本。
7. 精度基线稳定后才做 Model1 FP16、专项 TensorRT、INT8、剪枝、零拷贝和自定义 CUDA。

任何加速工作必须记录目标 NX 上的分项延迟、端到端 P95、吞吐、峰值内存、温度、功耗和精度变化，不能用 RTX 数据代替。

## 四、Agent 原始架构：4B + 9B，而非视觉模型 + 语言模型

必须准确理解原始目标：

```text
L0 Guardian（不依赖 LLM）
→ L1 确定性 Reflex
→ MEM 已验证经验
→ System 1：常驻 Qwen3-4B
→ 确定性 Escalation Router（尚未实现）
→ System 2：按需唤醒 9B（尚未部署）
→ 两模型共用 Authority / Guardian / Control / Verify / Rollback
```

- `System 1 = 4B`，负责常见语义诊断、受限工具提案和 abstain。
- `System 2 = 9B`，只处理复杂/未知/跨模块耦合或前序恢复失败事件。
- 当前代码中的 `L2` 是 4B，不是 9B。
- 9B 不拥有比 4B 更高的动作权限。
- “约 95% 由小模型处理”只是早期设计目标，没有实测分母，禁止当结果宣传。
- 截至交接，可确认落地的是 4B 单模型 P0，加 L0/L1/MEM；9B、自动升级路由和双模型闭环均未实现。
- 现有一次隔离 Replay 中，常驻 4B 对 `INSPECTION_PAUSED` 提议 `resume_inspection` 并达到 mission RECOVERED，只证明该次链路跑通，不等于 ASR/MTTR、生产恢复率或实物产线验证。

## 五、不要为了部署 Agent 而强行制造需求

对生产真正必要的是：

```text
Telemetry + 状态机 + Guardian + Control + Verify + Rollback + 审计
```

4B/9B 是否必要必须用对照实验回答。当前合理定位：

- EdgeMedic Lite 是可靠运行时核心。
- 4B 是默认只读/低风险的边缘运维助手和受限提案器。
- 9B 是条件性研究支线，在困难事件上证明有增益后才准入。

除了故障恢复，Agent 更值得做的项目内能力包括：

1. 主动复检：检测证据不足时请求第二视角、改变已批准的光照/转台方案、执行极坐标处理或转人工。
2. 工件级证据：聚合多帧、多视角、双专项与未来涡流/振动结果，形成可追溯 `part_id` 记录。
3. 检测配方调度：只在经过验证和签名的模型包、光照、相机与阈值配方间切换，失败回滚。
4. 难例回收：收集跨视角冲突、低置信、高光误报、新批次漂移和人工推翻案例，生成待标注队列；不得在线自动训练污染模型。
5. 设备验收：检查清晰度、曝光、ROI 稳定性、转台角度、极坐标中心误差、串口、P95、温度和长时稳定性。
6. 日志解释与自然语言查询：回答必须有结构化证据和 provenance，禁止自由编造。

Agent 不应直接替代视觉模型判定像素缺陷，也不应绕过确定性融合决定合格/不合格。它适合决定是否需要更多证据、如何安全复检、何时降级和何时请求人工。

## 六、Agent 接手后的 P0 安全审计

在增加 9B、工具或动作前，按以下顺序核实当前实现。不要只读文档，必须对照固定提交源码和测试。

1. `edgemedic/service.py`
2. `edgemedic/runtime.py`
3. `edgemedic/policy.py`
4. `edgemedic/adapter.py`
5. `edgemedic/reasoner.py`
6. `edgemedic/authority.py`
7. `edgemedic/client.py` 与 `readonly_client.py`
8. `edgemedic/memory.py`
9. `gp/control.py`、`gp/actions.py`、`gp/verify.py`、`gp/web.py`
10. `docs/midterm/runs/p0/final_system/` 原始证据

必须核实并优先修复：

- Control API 调用方身份、token/HMAC 或本机 socket 边界，不能仅相信请求体 source。
- Agent 服务所有 POST、GUI `/agent/*` 代理、控制租约和 recovery arm 权限。
- `observe_only` 与执行模式必须是服务端 fail-closed；不能只靠端口字符串区分生产和 Replay。
- LLM 不可用时，L0/Guardian/必要 Reflex 仍必须运行。
- 人工 Stop/Pause 与故障 Pause 必须区分；人工停线优先并立即撤销恢复授权。
- stale snapshot TTL、每个 episode 的单一活动决策、request ID 幂等、超时重试和并发竞态。
- `config`、`function`、`mission` 验证严格分离；仅 config 成功不得标记 RECOVERED 或写入成功记忆。
- Missing Hole 独立故障、shared worker、双专项任一失败和 `mission.output_valid` 契约。
- EpisodeStore 原子写、锁、版本迁移、环境绑定、TTL、在线污染与负迁移。
- 结构化日志应包含 commit、模型哈希、prompt/grammar 哈希、输入摘要、动作、Authority、Control、Verify 和前后快照。

生产路径采用严格 Grammar/Schema。不要依靠工具名编辑距离自动纠错；未知、歧义或非法输出应拒绝或 abstain。

## 七、4B→9B 的正确研发方式

不要使用一个随意的 `confidence < 0.72` 判断。4B 自报 confidence 未校准，不可直接信任。Escalation Router 应是确定性的，综合：

- 结构化输出是否有效；
- 4B 是否 abstain；
- 是否出现多模块冲突；
- L1/MEM/4B 是否未通过 function/mission Verify；
- 相同事件是否反复；
- 是否存在已准入且值得执行的动作；
- 9B 可用性、剩余时间、RAM/GPU、温度和视觉预算；
- 重试次数与人工升级规则。

建议路由结果：

```text
HANDLE_FAST
ESCALATE_DEEP
ABSTAIN
REQUEST_HUMAN
SAFETY_ONLY
```

两个模型必须使用同一内部结果契约，并显式区分：

```json
{
  "decision_layer": "MODEL",
  "model_tier": "FAST_4B",
  "diagnosis": "...",
  "evidence_codes": ["..."],
  "action": null,
  "abstain": true,
  "missing_evidence": ["..."],
  "escalation_recommended": true
}
```

这只是内部设计起点，正式实现前必须写 JSON Schema、版本和兼容测试。

9B 首先只读接入，记录提案但不执行。只有通过同一困难事件集的 `规则-only / 4B-only / 9B-only / 4B→9B` 配对实验，证明 9B 显著提高正确决策或高质量 abstain，才允许其提案进入共用安全链。

必须测量：准确率、错误合法动作率、危险提案拦截率、abstain 质量、决策延迟、token、加载峰值、视觉 P95 干扰、内存、温度、功耗、OOM 与恢复性。Orin NX 16GB 不应默认让 4B 和 9B 双常驻。

## 八、建议实施顺序

### Track A：视觉主线（项目成败的最高优先级）

1. 核对 `main-web` 与 `dataset` 的模型、配置、测试和报告。
2. 建立工件 ID、多视角采集与 group split 契约。
3. 机械/光照固定后实现几何归一化和齿圈极坐标展开。
4. 建立固定、可重复的单变量评测；不污染 blind test。
5. 达到精度门槛后再做 NX 部署优化。

### Track B：Agent v3（安全优先，研究支线）

1. 从 `integration/dual-specialist-edgemedic@ed9b525` 建立正确工作线。
2. 先复现或至少静态核对现有 4B P0，不改旧 frozen 证据。
3. 完成 P0/P1 安全与双专项契约修复。
4. 冻结 `ReasonerResult`、`RouterDecision`、`Incident` 版本化 Schema。
5. 用 mock 9B 实现并测试 Router，不立即下载或加载模型。
6. 接入只读 9B，进行资源与配对评测。
7. 根据结果决定保留、缩减或停止 9B 支线；不要预设双模型一定成功。

建议资源投入：视觉与机械约 70%，安全运行时约 20%，双模型可行性约 10%。

## 九、Git 和提交纪律

- 开始前检查工作树；不覆盖用户未提交更改。
- 每个提交只完成一个清晰目标，遵循 `<type>(<scope>): <summary>`。
- 文档改动运行 `git diff --check`。
- Python 改动至少运行相关 `py_compile` 和单元测试；前端改动运行构建。
- 无硬件或依赖导致无法验证时，明确说明，禁止伪称通过。
- 不改写或重新生成历史 frozen 证据。
- 不把外部桌面文件、临时日志、`.env`、缓存或秘密提交到仓库。
- 未经用户明确要求，不进行生产部署、NX 故障注入、systemd 安装或危险控制动作。
- 达到自然提交点时，由 Codex 负责检查 diff、验证、提交并报告 SHA；是否推送按用户当前指令执行。

## 十、你接手后的第一份交付

先不要大改代码。第一轮应交付一份基于实际源码的审计结果，包括：

1. 当前 checkout、所有相关分支和固定 SHA。
2. `integration/dual-specialist-edgemedic@ed9b525` 到当前 Agent 工作线的真实差异。
3. 当前 4B 完整调用链与所有实际 HTTP POST 路径。
4. 哪些路径 observe-only，哪些可能真实执行。
5. P0 安全问题，按严重程度和源码行号列出。
6. 双专项 Snapshot/Control/Verify 的契约缺口。
7. 现有测试实际运行结果及无法运行的原因。
8. 一个最小修复计划，每项包含验收条件，不先实现 9B。
9. 对 9B 在 NX 16GB 上的资源实验计划和 go/no-go 门槛。
10. 明确区分：已实现、已有记录证据、当前复验通过、建议设计、尚未完成。

不要只复述交接文档。源码、固定提交、测试和原始 JSON 才是实现真值。如果交接文档和源码冲突，以源码为准并报告冲突。

## 十一、最终方向

项目不是为了“在 Jetson 上跑两个大模型”而存在。正确目标是：

> 先把机械成像、多视角、极坐标展开和双专项检测做成可靠的实时质检主链；再以 EdgeMedic 提供独立于 LLM 的安全监控、验证和回滚，并让常驻 4B 与按需 9B 在严格资源预算和统一权限下处理少量真正需要语义推理的事件。双模型是否保留，必须由真实增益、资源成本和安全实验共同决定。

请以审计者和接手工程师的身份工作，不要继续 Cursor 式的无边界堆叠。优先减少错误结论、隐式权限和不可复现实验；每次修改都必须回答：它解决了哪个已证实问题，如何验证，失败时如何回滚。
