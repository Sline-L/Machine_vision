# GearPro技术报告 LaTeX版

此目录在原MineTemplate v2基础上改写，内容依据相邻`GearPro_技术报告/GearPro_技术报告.md`。保留五章正文、七组附录、12幅图及17条参考文献；正文图表及实验数字来自现有报告。本次不训练、推理或调整模型配置。

## 编译与修改

在本目录执行：

```sh
latexmk -xelatex main.tex
```

输出为`Output/main.pdf`。项目交付PDF另存于项目根目录`output/pdf/GearPro_技术报告.pdf`。

- `document.tex`：五章正文，可直接编辑。
- `TEX/frontmatter.tex`：标题、摘要、关键词和阅读说明。
- `TEX/appendices.tex`：详细附录。
- `TEX/references.tex`：保留原报告编号的17条文献，当前PDF直接读取此文件。
- `TEX/settings.tex`：A4版心、行距、章节、页眉页脚、表格和图注设置。
- `TEX/config.tex`：字体、颜色、PDF信息与链接配置。
- `TEX/package.tex`、`TEX/commend.tex`：依赖与语义命令。
- `pictures/report/`：正文和附录图片，已复制到模板内。
- `references.bib`：参考资料迁移用的BibTeX导出，当前编译不运行BibTeX；完整出版信息以`TEX/references.tex`为准。

若要从最新Markdown重新同步，先在本目录执行`python3 sync_report.py`，再编译。同步会覆盖正文、摘要、附录、参考文献及图片；手动编辑这些文件前应保留自己的版本。同步不会覆盖全局排版配置。

## 环境与交付

需要XeLaTeX、latexmk及常见TeX Live宏包。字体使用思源宋体（Source Han Serif CN）、Noto Sans CJK SC、Nimbus Roman、Nimbus Sans及DejaVu Sans Mono；其他机器可在`TEX/config.tex`替换字体。

PDF中的目录、论文引用及内部资料跳转可直接使用；论文外链需要网络，原始实验资料的本地链接需要完整项目目录，源码包不包含模型和数据集。

原模板含编译产物的完整备份保存在相邻`MineTemplate v2_改写前_20261007`目录。`Output/verification.json`记录最终页数、内容结构、数值片段及编译日志检查。分页与图表经过PDF渲染检查。
