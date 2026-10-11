#!/bin/bash
# 一键编译所有进展小结相关 LaTeX 文档
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "=== [1/4] 编译 前期项目研究总结 ==="
xelatex -interaction=nonstopmode main_前期项目研究总结.tex
xelatex -interaction=nonstopmode main_前期项目研究总结.tex

echo "=== [2/4] 编译 项目后期研究方案 ==="
xelatex -interaction=nonstopmode main_项目后期研究方案.tex
xelatex -interaction=nonstopmode main_项目后期研究方案.tex

echo "=== [3/4] 编译 GearPro_项目进展情况小结 (完整版) ==="
xelatex -interaction=nonstopmode main_GearPro_项目进展情况小结.tex
xelatex -interaction=nonstopmode main_GearPro_项目进展情况小结.tex

echo "=== [4/4] 编译 GearPro_项目进展情况小结 (精简版) ==="
xelatex -interaction=nonstopmode main_GearPro_项目进展情况小结_精简版.tex
xelatex -interaction=nonstopmode main_GearPro_项目进展情况小结_精简版.tex

echo "=== 全部编译完成！生成的 PDF 列表： ==="
ls -lh *.pdf
