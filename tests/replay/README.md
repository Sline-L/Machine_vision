# Replay smoke pack

Place a **non-locked** pack here (or pass any pack directory to `--replay`).

```text
tests/replay/
├── replay_manifest.json
└── frames/
    ├── 000001.jpg
    └── ...
```

Build from `Machine_vision_dataset` **train/val gear frames**, never `test_scratch`:

```bash
python -m gp.replay --source /path/to/Machine_vision_dataset/dataset_gear/images/train \
  --dest tests/replay --source-commit <dataset SHA> --limit 40
```

Frames are gitignored. The manifest is committed after a pack is built so experiments can record `replay_pack_id` and `replay_pack_hash`.
