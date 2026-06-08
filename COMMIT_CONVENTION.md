# Commit Convention

本项目使用简化版 Conventional Commits，提交信息保持清晰、可检索、便于后续生成变更记录。

## 格式

```text
<type>(<scope>): <summary>
```

示例：

```text
docs(readme): add project setup guide
fix(detection): apply selected detection interval
refactor(ui): split camera display widget
```

## Type

- `feat`: 新功能
- `fix`: 修复缺陷
- `docs`: 文档变更
- `style`: 代码格式、空白、命名等不影响行为的变更
- `refactor`: 重构，不新增功能也不修复缺陷
- `perf`: 性能优化
- `test`: 测试相关
- `build`: 构建、依赖、打包相关
- `ci`: CI/CD 相关
- `chore`: 维护性变更
- `revert`: 回滚提交

## Scope

`scope` 使用小写英文，优先选择受影响的模块或领域：

- `camera`: 摄像头采集与显示
- `detection`: YOLO 检测流程
- `serial`: 串口通信
- `ui`: PyQt 界面
- `model`: 模型加载、权重、导出
- `config`: 配置项、路径、参数
- `docs`: 文档
- `repo`: 仓库结构、Git、工程配置

如果一次提交跨多个领域，选择最主要的 scope。确实无法归类时可以省略 scope：

```text
chore: initialize repository
```

## Summary

- 使用英文，祈使句或短动词短语。
- 首字母小写。
- 不以句号结尾。
- 建议不超过 72 个字符。
- 只描述这次提交实际完成的事情。

推荐：

```text
fix(serial): throttle duplicate result messages
docs(repo): add commit convention
```

避免：

```text
update code
fix bug
WIP
```

## Body

简单提交不需要 body。涉及设计取舍、兼容性、风险或迁移步骤时添加 body：

```text
refactor(config): move runtime options into config module

Replace hard-coded camera, serial, and model values with a single
runtime configuration object. Keep current defaults unchanged.
```

## Breaking Changes

如果变更会破坏原有接口、命令或配置方式，在 footer 中写明：

```text
BREAKING CHANGE: model path must now be configured in config.yaml
```

## 提交前检查

每次提交前至少执行：

```bash
git status --short
git diff --check
git diff --stat
```

如果改动了可运行代码，尽量执行对应验证命令，例如：

```bash
python -m py_compile gp_main.py gp_mainwindow.py gp_cameradisplaywidget.py gp_detectiondisplaywidget.py gp_detectionworker.py gp_globals.py gp_serial.py
```

如果无法运行验证，需要在最终说明中明确原因。
