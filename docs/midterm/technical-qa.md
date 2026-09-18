# 中期答辩技术问答（≥15）

答案均对应本仓库真实代码/文档口径。未完成能力如实说明。

---

**1. Agent 与普通规则系统有什么区别？**  
规则（L0/L1）处理已知故障；另有 EpisodeStore 记忆路由与可选 L2 小模型。Agent 读 Snapshot、出白名单动作意图，执行交给 Control/Verify，而不是在规则脚本里直接改硬件。

**2. 为什么使用 Qwen3-4B？**  
边缘可部署的小模型，用于规则未覆盖的故障提案；配合工具白名单与 grammar，限制输出空间。不是通用聊天机器人。

**3. 为什么不是所有故障都用 LLM？**  
延迟、token、幻觉风险。`CAMERA_STALE` 等应用 L1 毫秒级确定性处理（见 `edgemedic/policy.py`）。

**4. RQ1 结构化状态优势是否成立？**  
仅在 family-limited 设定下有证据；不得外推普遍优势。存在大量双失败与成本代价（见技术报告 §8）。

**5. 为什么 21/30 双失败？**  
说明结构化状态不是万能；许多 case 上 raw 与 structured 都失败。应诚实讲失败模式，而不是只报 win。

**6. EpisodeStore 如何防止错误经验污染？**  
config 级验证不入库；需 function/mission；命中要重复成功次数 ≥3 且 wins>fails（`memory.py`）。单次成功不成规则。

**7. MEM 与 L2 如何路由？**  
L1 未出动作且冷却允许时查 MEM；命中则提案并（正式环路）可跳过 L2。未命中才考虑 L2。中期 Demo 用 cooldown 模拟「L1 已尝试」以展示 MEM。

**8. Authority 如何约束动作？**  
正式路径：HTTP Control 赋 `authority=agent`，`bind_source` 禁止自称 human；accept 白名单预检。中期 Demo **不调用** Authority，只标注需要 Control accept。

**9. L1/MEM 为什么未必走与 L2 相同的 Authority？**  
历史设计里 reflex/memory 源直接进 Control。这是已知局限；统一闸门应是 Control accept + Verify，而不是「LLM 才危险、规则就绝对安全」。

**10. Control 与 Web 如何避免并发乱改？**  
Web：lease；变更经 `human_action`。Control：`_action_lock`。Guardian：紧急 hold **不**等待长锁（Step 6.3）。

**11. Guardian 如何抢占普通恢复？**  
`assert_emergency_hold` 置位并 pause；`rebuild_inspector` 阶段检查 generation，禁止 hold 下 resume。

**12. 双专项 Verify 如何判断恢复？**  
需双专项加载与窗口后新输出；`cap_verify_level` 在证据不足时降级；SAFE_STOP mission ≠ 检测恢复。

**13. Shadow observation 是什么？**  
V3-1：观察不驱动恢复（`drives_recovery=false`），holdout 未动。

**14. 为什么没有使用 fresh holdout？**  
研究协议冻结；防止调参污染最终测试。中期也禁止。

**15. Agent 是否已经完成真实硬件部署？**  
否。NX overlay 有历史验收，但不在 Git；本 Windows 集成分支交付的是只读 Demo + 集成到 6.3 的 Runtime/Control。

**16. 技术创新点是什么？（勿夸大）**  
有界边缘自治：结构化 Snapshot、分层决策、经验门控、Control/Verify/Guardian 与双专项检测同分支集成；中期强调 propose/execute 分离。

**17. 中期之后还需要做什么？**  
Agent 只读常驻对接 GET state；有条件开放经 Verify 的自动恢复；overlay 入库；调用者认证；实模型与真机验证；温度遥测接线。

**18. 现场看到 RECOVERED 吗？**  
本次 observe-only **不得**报 RECOVERED。历史 Demo A/B/C 的 RECOVERED 仅作 FROZEN REPLAY。

**19. `python -m edgemedic` 能直接演示吗？**  
不建议。该入口含执行环路。请用 `tools/agent_midterm_demo.py`。

**20. 双专项 Missing Hole 坏了 Agent 会怎样？**  
Step 6.3 Snapshot 可标独立 `error_state`；旧 L1 仍主要看顶层 scratch 字段。完整双专项故障族扩展是后续工作。
