# Replay smoke images

Place **non-locked** JPEG/PNG frames here (or pass any directory to `--replay`).

Do **not** copy `test_scratch`. That set is locked: it must not be used to retrain, retune thresholds, or as a dirty smoke set that later masquerades as evaluation.

Suggested smoke mix: a handful of ordinary production-like frames from non-test splits, plus a few locator-friendly gear images. Replay only manufactures real inference cycles; it is not a substitute for the locked test protocol.
