---
name: advisor-review-2026-10
description: "Advisor (导师) critique of the GearPro midterm PPT/report, Oct 2026 — what reviewers care about and what to avoid in report writing"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 8c8ffb92-12c7-4080-ab6a-10f0d1f10b4c
  modified: 2026-10-08T06:14:08.636Z
---

Advisor feedback relayed by the user (~2026-10-08) on the GearPro SRTP stage PPT/report:
- Reviewers must understand from scratch: 任务是什么、关键技术是什么、有无详细文献综述、整体技术路线. Structure must match content. Midterm/结项 judge process completion, technical route, and outputs (论文/专利), not whole-machine acceptance or strict KPI validation — weaken 整机验收, a demo design is enough. Images matter more than video.
- Innovation framing: application scenario + choosing/adapting networks for it (e.g. tuning a network for gears), not new methods. Describe the application scenario precisely (conveyor carries one gear at a time; multi-gear-per-frame ROI talk is unrealistic).
- Metrics: advisor did not know recall/precision; use the target field's established metric system and cite it; never invent metrics. Learn the Neyman–Pearson criterion. Simulate realistic data where normal parts dominate.
- Parameters: fusion weights 0.25/0.75 and threshold 0.3003 were heavily criticised — must be justified by real tuning (e.g. Bayesian optimisation) against a proper metric system, with enough test metrics; a threshold far below 0.5 needs explanation. Don't assume; simulate or measure.
- Cut trivial details (ROI 4% expansion, difficult-sample labelling). ROI expansion can add background. Don't disparage others' methods or call them unreliable; the unified model may just be under-tuned. Don't use AI-coined terms (e.g. 双专项).
- Every English abbreviation must be spelled out at first use. Claims need data validation and literature support ("someone used a similar method and it worked").
- Other asks: lighting study (diffuse vs specular / shadowless), Jetson study (why it is fast, exploit its architecture), GUI redesign (small window, bigger buttons).

**Why:** the PPT left the advisor confused and the user was scolded for the weights/threshold/metrics.
**How to apply:** check every report/PPT edit against this list. Related: [[gearpro-report-decisions]], [[repo-docs-are-ai-written]]
