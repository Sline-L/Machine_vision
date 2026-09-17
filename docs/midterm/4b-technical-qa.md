# P0 4B 技术问答

**Q: Agent 与纯规则系统有何不同？**  
A: L0/L1 仍是确定性规则；未知故障可进入 Qwen3-4B（L2）生成结构化提案，再经 Authority/Control，而不是规则表穷举。

**Q: 4B 真正负责什么？**  
A: 在 L1/MEM 未收口时，输出 `{tool, params}` 诊断提案。不直接操作硬件。

**Q: L0/L1/MEM/L2 如何协作？**  
A: 热保护 L0 → 已知故障 L1 → 经验 MEM → 否则 L2。见 `edgemedic/runtime.run_once`。

**Q: 为何引入 EpisodeStore？**  
A: 复用已验证成功动作，跳过秒级 L2。单次成功不会变成规则（需 ≥3）。

**Q: 如何防止错误经验？**  
A: 仅 `verify_level` 为 function/mission 才记成功；config/none 不入成功库。

**Q: 为何 4B 不直接执行？**  
A: 模型不可靠。Authority 对高风险工具强制 DRY_RUN；执行只走 Control 白名单。

**Q: Authority 与 Control 区别？**  
A: Authority 决定 L2 是否允许自动执行；Control 做 precondition、执行与 Verify。

**Q: Guardian 做什么？**  
A: 热保护 / emergency hold；普通 Agent 恢复不能解除 hold。

**Q: 双专项 Verify？**  
A: Control 轮询后 `cap_verify_level`；mission 级需双专项输出证据（control_view）。

**Q: 4B 幻觉/非法工具？**  
A: GBNF + whitelist 解析；非法/解析失败 → 拒绝，不“猜”一个动作。

**Q: 超时/服务崩溃？**  
A: `ReasonerError` → 安全失败，不执行。

**Q: 为何 9B 未接入？**  
A: P0 唯一目标是 4B。9B 复用同一提案协议，待 4B 验收后再开。

**Q: 中期后如何加 9B？**  
A: 增加 reasoner 后端选择与协作策略；不改 Control 白名单边界。

**Q: 创新与局限？**  
A: 创新：双专项 Snapshot + 分层 Agent + 真 4B + 隔离 Replay 恢复。局限：无 4B 执行闭环、无真机恢复、无生产上线。
