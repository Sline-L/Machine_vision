# 阶段 0 实验目录

规格见 `reports/papers/阶段0_运行手册.md`，各角色的交接提示词见 `reports/papers/阶段0_交接提示词.md`。

本目录只放阶段 0 的新脚本与小体积结果。不得修改 `gp/`、`model/`、`ultralytics/` 和仓库根目录的现有入口脚本。

```text
experiments/phase0/
  README.md
  STATUS.md            各角色每完成一步就追加一行（时间、角色、步骤、结果）
  common/              三个角色共用的小函数（融合、温度缩放、哈希、CSV 写入）
  pc/                  PC 侧脚本（P 系列任务）
  jetson/              Jetson 侧脚本（J 系列任务）
  analysis/            分析侧脚本（A 系列任务）
  results/             进 git 的小文件：CSV、JSON、情报单、图
    env/  pc/  jetson/  analysis/  reports/
  data/                不进 git：预处理张量、图像副本、校准缓存
  engines/             不进 git：ONNX 与 TensorRT 引擎
  logs/                不进 git：tegrastats 原始日志、构建日志
```

## 分支与协作协议

所有工作都在分支 `claude/jetson-defect-detection-cascade-dbbf33`。多个 AI 并行时：

1. 每个角色只写自己的子目录，不改别人的文件。
2. 推送前先 `git pull --rebase origin claude/jetson-defect-detection-cascade-dbbf33`。
3. 只提交小文件。张量、引擎、ONNX、校准缓存、原始日志一律不提交，由 `.gitignore` 排除。
4. 提交信息遵守 `COMMIT_CONVENTION.md`，例如 `feat(phase0): add jetson build script`。
5. 不用 `git add .`，按文件添加。
6. 不做 force push，不改 git 配置。
7. 大文件靠 rsync 或 scp 传输，哈希记录在 `results/` 的 manifest 中。
