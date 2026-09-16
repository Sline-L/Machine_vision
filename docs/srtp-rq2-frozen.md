"""RQ2 freeze. Do not farm pause or CAMERA_STALE repeats for larger n."""

STATUS = """
RQ2 STATUS

Live verified memory signatures:
  INSPECTION_PAUSED
  CAMERA_STALE

Cross-fault mechanism:
  VERIFIED

Observed effects:
  - can bypass L2 for previously solved fault pattern
  - can reduce recovery latency by avoiding L2
  - can avoid exposure to an incorrect L2 proposal in observed case

Recovery-success improvement:
  NOT ESTABLISHED

General effectiveness:
  NOT YET VALIDATED
"""
