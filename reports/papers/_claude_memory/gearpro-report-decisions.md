---
name: gearpro-report-decisions
description: "User's 2026-10-08 decisions for restructuring the GearPro 齿轮外观缺陷检测系统技术报告 (audience, structure, voice, facts)"
metadata:
  node_type: memory
  type: project
  originSessionId: 8c8ffb92-12c7-4080-ab6a-10f0d1f10b4c
  modified: 2026-10-08T14:54:52.568Z
---

Decisions confirmed by the user on 2026-10-08 for the stage technical report:
- Audience: SRTP 阶段/结题评审. Voice: 项目组 ("本项目"), no personal division of labor, do not compare against 申报书 KPIs. Agent/EdgeMedic is excluded from the report (and not planned to be added to the project for now).
- Structure: system-first — 引言 → 系统总体设计 → 数据集 → 检测方法 → 选型实验 (V3/V4 compressed into one section) → 测试结果与分析 → 结论与下一步. Hedges consolidated into a 局限性 section; source links moved to captions and 附录B.
- Edit the LaTeX directly (no more sync_report.py from the Markdown); update verify_report.py to the new structure. Deliver into repo `reports/technical-report/` and commit.
- Facts: board is Jetson Orin NX; the rig has upper/lower two cameras, designed as per-camera detection + OR, but all current testing and the dataset use a single camera. NX latency: cite the replay measurements (locator TRT p95≈27 ms, scratch subsystem p95≈181 ms, total p95≈220–244 ms) and state they exclude the missing-hole subsystem and are not whole-machine tests.
- Abstract carries no abbreviation glosses (user annotated their removal, commit 46b2f32); full names go at first use in the body instead. Don't re-add them to the abstract.
- Structure later changed per advisor (2026-10-08 evening): 引言 → 国内外研究现状 → 技术路线 → 系统 → 数据 → 方法 → 选型 → 结果 → 结论, 9 chapters.
- Writing style reference: github.com/Leey21/awesome-ai-research-writing (one idea per paragraph, conclusion-first, plain academic Chinese, no bold lead-ins).

Related: [[gearpro-project-map]]
