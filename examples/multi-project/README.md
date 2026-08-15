# Multi-project and multi-style example / 多项目多风格示例

This synthetic example expands one reconstruction job across two projects and three style profiles. It contains no private art.

该合成示例将同一个重建任务展开到两个项目和三套风格配置，不包含任何私有美术资源。

```powershell
python examples/multi-project/create_reference.py
ui-rebuilder workspace plan examples/multi-project/workspace.yaml
ui-rebuilder workspace build examples/multi-project/workspace.yaml --max-workers 3 --skip-openpencil --force
ui-rebuilder workspace validate examples/multi-project/workspace.yaml
```

Remove `--skip-openpencil` to produce a complete five-page `.fig` package for every matrix entry.

移除 `--skip-openpencil` 后，每个构建矩阵条目都会生成完整的五页 `.fig`。

Outputs / 输出：

```text
Output/multi-project/
  cultivation-demo/ink/training/
  cultivation-demo/dark/training/
  space-demo/neon/dashboard/
  workspace-build.json
  workspace-validation.json
```
