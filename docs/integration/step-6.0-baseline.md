# Step 6.0 集成基线

记录时间：2026-09-16（工作树创建时）

## Git

| 项 | 值 |
|---|---|
| 集成分支 | `integration/dual-specialist-edgemedic` |
| 工作树 | `G:\CODE\Machine_vision-dual-specialist` |
| 起点 | `main-web` `de608d9f96366ca1f06c88b99ddf10cefab35eee` |
| 自治来源 | `srtp-web` `cfdbbe8ffcbfc8c4b4e34431f0eab8b69abfe81e` |
| merge-base | `1b54d748bb6bfa59fd537dd0838250210ede7746` |
| 上游跟踪 | 已取消（避免误推 `origin/main-web`） |

未改动：`main-web`、`srtp-web`、`main`、`srtp`、experiment 工作树、NX overlay。

## 环境

- 系统 `python`：MSYS `C:\msys64\mingw64\bin\python.exe`（无 torch）
- 仓库 venv：`G:\CODE\Machine_vision\.venv` Python 3.12.14（无 torch）
- 本工作树无独立 `.venv`

## 模型权重（真实文件，非 LFS pointer）

| 文件 | 大小 | 文件头 |
|---|---|---|
| `model/model1.pt` | 20740933 | PyTorch ZIP (`PK`) |
| `model/model2/classifier_1.pt` | 16314725 | `PK` |
| `model/model2/classifier_2.pt` | 44780619 | `PK` |
| `model/model2/detector.pt` | 5902651 | 存在 |
| `model/missing_hole_v1/classifier_1.pt` | 16314725 | `PK` |
| `model/missing_hole_v1/classifier_2.pt` | 44780619 | `PK` |
| `model/missing_hole_v1/detector_3.pt` | 5377541 | `PK` |

`git lfs ls-files` 仅列出 missing_hole 三权重；checkout 后均为完整二进制，不是 `version https://git-lfs.github.com` 指针。

## 基线测试（修改前，`python -m unittest tests.test_gearpro_core tests.test_web tests.test_telemetry tests.test_profiles tests.test_gp_app -v`）

| 测试 | 结果 | 原因 |
|---|---|---|
| `test_specialists_use_or_decision` | PASS | 纯数据类型 |
| `test_v1_and_v2_return_matching_versions` | PASS | 不加载模型 |
| `test_snapshot_has_v2_specialists` | PASS | 不加载模型 |
| `ScratchV5Tests.test_real_model_bundle_loads_on_cpu` | ERROR | `ModuleNotFoundError: torch` |
| `MissingHoleV1Tests.test_real_model_bundle_loads_on_cpu` | ERROR | `ModuleNotFoundError: torch` |
| `test_config_resolves_relative_weights_and_checks_hashes` | FAIL | Windows 短路径 vs `Path.resolve()` |
| `test_config_resolves_weights_and_checks_hashes` | FAIL | 同上 |
| `test_video_and_bind_arguments` | FAIL | `Path` 在 Windows 上为反斜杠 |
| 其余所列模块用例 | PASS | 见当时 41 条中的 ok |

`test_real_model_bundle_loads_on_cpu` 记为 **环境 ERROR**，不是双专项代码故障。权重文件已存在。未修改测试期望来掩盖该环境缺口。
