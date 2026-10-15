---
name: gearpro-project-map
description: "Where GearPro code, branches, report sources, and hardware facts live (two local clones, report LaTeX pipeline, board model)"
metadata:
  node_type: memory
  type: project
  originSessionId: 8c8ffb92-12c7-4080-ab6a-10f0d1f10b4c
  modified: 2026-10-08T04:52:02.419Z
---

- Two local clones of Sline-L/Machine_vision: `D:/Files/CODE/Machine_vision/Machine_vision` (main, feat/ui-redesign, srtp, archive-old, origin/dataset) and `D:/Files/CODE/SRTP for codex` (main-web, srtp-agent/v2-pressure-pilot with EdgeMedic midterm evidence, dataset, local-workspace with SRTP application/plan/budget, feature/multiview-polar-unwrapping = handoff doc only). Branch `integration/dual-specialist-edgemedic@ed9b525` is cited but not present in either clone (as of 2026-10-08).
- The stage technical report (齿轮外观缺陷检测系统技术报告, 2026-10-07) is LaTeX in a "MineTemplate v2" zip the user sends via QQ; `sync_report.py` regenerates frontmatter/body from `GearPro_技术报告.md` (not on this PC), so abstract edits must also go into that Markdown. Fonts: Source Han Serif CN / Noto Sans CJK, not installed on this PC.
- Board is Jetson Orin NX 16GB (budget doc, TRT 10.7.0, 15 GiB host), but most docs/report just say "Jetson NX". Runtime code uses a single camera although reports describe upper/lower dual cameras.

**Why:** the user expects broad cross-branch understanding before report/writing work; facts are scattered across clones.
**How to apply:** check both clones and the report-vs-code mismatches above before writing about the project.
