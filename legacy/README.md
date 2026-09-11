# 旧版代码归档

此目录保留重构前的程序和实验脚本，不再参与新版程序运行。

旧版主程序仍可从项目根目录直接启动：

```bash
python legacy/gp_main.py
```

也可以运行早期单文件版本：

```bash
python legacy/new1.py
```

旧版默认硬件参数保持不变：摄像头索引 `2`、串口 `/dev/ttyHS1`、波特率
`9600`。两个旧入口默认使用根目录的 `best.pt`，也可用环境变量 `GP_MODEL_PATH`
临时指定其他模型。

新版入口为项目根目录的 `gearpro_main.py`。
