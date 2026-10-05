# GearPro 汇报与交付资料

`reports/` 集中保存不参与 GearPro 运行的汇报和文档资产。

```text
reports/
├── stage-report/
│   ├── beamer/          # LaTeX 源文件、图片和正式 PDF
│   ├── notes/           # 讲稿、大纲和过程记录
│   └── deliverables/    # 正式 DOCX、PDF 和 PPTX
├── templates/               # 可复用文档模板
└── references/              # 本地参考资料，默认不提交
```

## 收纳规则

- 跟踪可维护的源文件、汇报素材和需直接交付的正式成品。
- 不跟踪 LaTeX 编译中间文件、临时导出、日志或只用于参考的大型原始文件。
- 运行时模型只放在 `model/`，评估结果放在 `artifacts/evaluations/`。
- 移动已跟踪文件时使用 `git mv`，保持历史可追溯。
