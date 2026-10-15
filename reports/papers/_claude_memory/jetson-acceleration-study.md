---
name: jetson-acceleration-study
description: "Status of the advisor-requested Jetson speed/power study (Oct 2026) — tooling exists, no NX numbers yet"
metadata:
  node_type: memory
  type: project
  originSessionId: bf2735a4-b5b4-44a2-9ae5-b1c4ca3b0946
  modified: 2026-10-08T15:13:58.498Z
---

On 2026-10-08, export and benchmark tooling for the Jetson study was committed on branch claude/frosty-payne-92678b (1892d66 code, 2f3885b docs/jetson-acceleration.md).

The tooling is `python -m gp.export_engine specialists` and `python -m gp.bench run|compare|report`. It has run only on the dev laptop CPU. The TensorRT and DLA paths have never been executed, and the team must run them on the NX.

A follow-up commit, 9ca03af, adds the DLA-parsing fix and raw sensor logs.

With user approval, the branch was pushed to GitHub as `feat/jetson-bench` (e383f46, main + 4 commits) on 2026-10-08. The NX checkout is on srtp, which lacks this code. docs/jetson-acceleration.md section 7 therefore tells the team to `git worktree add /home/jetson/Projects/Machine_vision-bench` from origin/feat/jetson-bench and not to switch branches in the srtp checkout.

A duplicate GPT implementation also exists: commit 6d2c277 in "D:/Files/CODE/SRTP for codex" on branch feature/multiview-polar-unwrapping. That branch is based on a stale Sept tree. On 2026-10-08 the user chose the Claude version, and the GPT commit was reverted by 9edcf8a on that branch (local only, not pushed).

Literature survey (2026-10-08, commit 590b6cd on claude/gallant-swanson-e18bed, `reports/research/GearPro_技术路线与文献调研.md`, ~90 verified refs + 6 patents): "detector on GPU, classifier on DLA" on Orin NX is already a 2026 preprint (Raju, arXiv:2608.11770), and Tayal 2025 shows DLA can slow things via contention. Novelty must be framed as mapping the whole inspection cascade + J/part + per-part verdict consistency, not "using DLA/TensorRT". Metric system chosen: AIAG MSA 4th ed. (漏检率/误检率/有效性/Kappa); threshold via NP (Tong 2018 order-statistic rule, needs ≥59 defect parts at α=δ=0.05).

**Why:** the SRTP advisor asked for Jetson architecture justification plus a latency/power comparison with accuracy unchanged ([[advisor-review-2026-10]]).

**How to apply:**
- Never quote speed-ups or power numbers until summary.json files from the NX exist.
- The only real NX numbers are the srtp 2c79075 locator/scratch baseline.
- The accuracy tolerances in the doc are proposals and must be frozen with the advisor before running.
- Run the locked test set once only, as migration regression.
