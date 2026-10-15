---
name: jetson-survey-latex
description: "Standalone Jetson-deployment survey being written in LaTeX (started 2026-10-09): where it lives, what is done, and the honesty rules for it"
metadata:
  node_type: memory
  type: project
  originSessionId: 632bd876-7ac2-41e0-b5b4-db17820b6b94
  modified: 2026-10-09T07:14:57.934Z
---

The user decided on 2026-10-09 to write an independent literature survey (not just paper material) on Jetson deployment/acceleration for industrial vision inspection, in LaTeX, keeping the evaluation-methodology section, Jetson only (no FPGA/phone NPUs).

Source lives in `reports/papers/jetson-survey/` (worktree reverent-pascal-e61bd1, uncommitted): `main.tex`, `sections/01..10`, `refs-lit/plat/app/doc.bib`, built with `latexmk -xelatex -outdir=build main.tex`; `gbt7714-numerical` style. Sections 1, 2, 7 are drafted; 3–6, 8–10 are stubs with red `\todo{}` plans. Companion notes: `reports/research/GearPro_Jetson部署与加速文献综述.md`.

**Why:** the user is new to the field and wants a survey they can learn from and possibly submit.
**How to apply:** red `\todo` marks anything from abstracts, titles, or prior-note hearsay; clear them only after reading the paper's body. No NX measurements of our own go in. CNKI/Chinese literature is still missing and must come from the user. Don't claim a systematic search (no PRISMA-style record exists). Related: [[jetson-paper-directions]], [[baoyan-paper-rules]], [[advisor-review-2026-10]]
