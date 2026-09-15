# Skip-detector latency pretest

- crops: 34
- locator: `model/model1.pt` (PT)
- FULL v5 stage-sum p50/p95: 117.62 / 275.646 ms
- classifiers-only p50/p95: 46.503 / 61.974 ms
- Δp95 (FULL−cls): 213.672 ms
- ratio cls/full p95: 0.2248
- worth_continuing (advisory): True

FULL detector p50/p95: 67.895 / 214.428 ms

Does **not** open CLASSIFY_ONLY or change Mission.
