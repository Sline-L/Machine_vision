# 情报单 G0（Jetson 部分）

时间: 2026-10-16T19:00+08:00 / 执行者: Composer / 路径: `/home/jetson/Projects/Machine_vision-phase0`（未改动 `Projects/Machine_vision` 现网树）

状态: **OK**

已完成步骤:
- J0：`results/env/jetson_env_raw.txt`、`jetson_env.json`
- J1：接收 PC 张量 + ONNX；**1028** 行 manifest 逐文件 SHA256 **0 缺失 0 不一致**（`results/jetson/j1_summary.json`）
- J2：`MAXN_SUPER` + 用户执行 `jetson_clocks` 锁频（见 `results/jetson/j2_power.json` 与用户终端记录）

未完成与原因:
- J3–J9：手册规定 **G0 门禁**，决策者放行前不构建引擎、不采 Jetson 分数

关键事实:
- L4T **R36.4.7**；板型 Orin NX Super
- TensorRT **10.7.0**（Python + `/usr/src/tensorrt/bin/trtexec`）；**trtexec 不在 PATH**
- PyTorch **2.5.0a0+872d972e41.nv24.8**（J0 记录）；磁盘可用 **103 GB**
- 锁频后：CPU **1984 MHz**；GPU **1173 MHz**；EMC **3199 MHz**；风扇 **pwm=127**（nvfancontrol，非满速）
- `gearpro.service` / `edgemedic.service`：**inactive + disabled**（用户同意后已停并取消自启）
- 张量路径：`experiments/phase0/data/tensors/`；ONNX：`experiments/phase0/engines/onnx/`

验收结果:
- J0: 通过（TRT 10.7 一致，磁盘 ≥20G，J0 时 GR3D 空闲）
- J1: 通过（1028/1028 SHA256）
- J2: 通过（MAXN_SUPER + jetson_clocks 已锁；环境温度 **未知**）

异常与意外:
- J0 情报中 `gearpro_service_seen` 已过时；重启后已确认服务未拉起
- 免密 sudo 仍不可用；J2 锁频由用户手动 sudo 完成
- SSH `RemoteForward 17897` 失败时需 `-o ExitOnForwardFailure=no`

请决策者回答的问题:
1. 风扇 pwm=127 是否足够 INT8 构建，还是实验前必须拉满？
2. G0 放行后 J4 构建是否使用 **4 GB** workspace（手册待定默认值）？
3. 是否同步启动分析侧 A1–A6 合成数据脚本（真实 scores 已有 PC 部分）？
