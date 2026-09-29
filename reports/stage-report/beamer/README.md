# GearPro 东南大学配色 Beamer 模板

本目录以原 THU Beamer Theme 为基础，调整为东南大学校徽的黄绿色视觉体系。

- 主色：东南大学深绿 `#3D6016`
- 强调色：校徽黄 `#FFCC00`
- Logo 来源：`pic/原配色.svg`
- 主题入口：`\usepackage{SoutheastUniversity}`

使用 XeLaTeX 编译：

```bash
cd reports/stage-report/beamer
latexmk -xelatex slide.tex
latexmk -xelatex GearPro_stage_report_full.tex
```

`slide.tex` 是五页测试稿，`GearPro_stage_report_full.tex` 是 GearPro 阶段汇报。
对应的正式 PDF 继续跟踪，`.aux`、`.fls`、`.nav` 等编译中间文件不提交。

## 原模板来源

最初能追溯到的版本是 [https://www.latexstudio.net/archives/4051.html](https://www.latexstudio.net/archives/4051.html)

我在16年的时候魔改了一发，20年的时候小修了一下，变成现在这样

Overleaf模板位于：[https://www.overleaf.com/latex/templates/thu-beamer-theme/vwnqmzndvwyb](https://www.overleaf.com/latex/templates/thu-beamer-theme/vwnqmzndvwyb)，可以直接点开

其中的教程部分参考了大鹰团长的介绍：[https://tuna.moe/event/2018/latex/](https://tuna.moe/event/2018/latex/)
