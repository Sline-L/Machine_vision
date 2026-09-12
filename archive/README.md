# 历史归档

这里保存当前训练主线不再直接使用的代码和旧说明。原始数据、模型权重、训练日志及测试报告仍保留在项目根目录的 `dataset_*`、`runs/` 和 `outputs/` 中。

## 代码

### `code/stage1/`

- `organize_dataset.py`：最初的图片重命名和数据拆分。
- `prepare_yolo_dataset.py`：Pascal VOC XML 转 YOLO 标签。
- `train_yolo26n.py`：第一阶段齿轮检测训练。
- `post_training_pipeline.py`：第一阶段测试、伪标签和裁切后处理。

这些脚本使用旧目录名 `DATASET/`，而当前数据目录为 `dataset_gear/`，因此仅作为历史记录保留。

### `code/v1/`

- `prepare_defect_temp_dataset.py`：准备早期 140 张缺陷数据。
- `train_defect_model.py`：早期 scratch/missing_tooth 双类别训练。
- `prepare_scratch_dataset.py`：准备 211 张单类划痕数据。
- `train_scratch_model.py`：单类划痕训练。

### `code/v2/`

- `auto_optimize_defects.py`：V2 自动候选训练和选择。
- `optimize_scratch_tiled.py`：划痕滑窗和局部放大实验。
- `evaluate_final_defects.py`：V2 最终测试评估。

V2 的三个脚本应视为一个整体；后两个脚本会导入 `auto_optimize_defects.py`。

## 旧文档

`docs/v1-v3/优化方案.md` 及 `docs/v1-v3/assets/` 保存早期方案、截图和结构图。

## 使用限制

归档脚本中的 `ROOT = Path(__file__).resolve().parent` 是按脚本原来位于项目根目录编写的。移动后路径不会自动指向项目根目录，因此不要直接把归档脚本当作当前训练入口。需要复现实验时，应先复制到隔离分支或显式修正数据、权重和输出路径。

