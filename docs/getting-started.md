# 使用指南

[简体中文](getting-started.md) | [English](getting-started.en.md)

本文介绍如何从一个干净的仓库开始安装 UI Rebuilder、创建重建任务、输出 `.fig`，以及按需启用 ComfyUI。

## 1. 环境要求

最低要求：

- Windows、macOS 或 Linux；
- Python 3.11+；
- Git；
- Bun 1.3.5，用于首次还原和构建 OpenPencil。

ComfyUI 属于可选能力。启用它时需要与所选 PyTorch 版本兼容的 GPU 驱动；无 GPU 仍可使用 UIIR、确定性图片处理和 `.fig` 输出。

## 2. 安装核心程序

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

Linux/macOS 使用 `source .venv/bin/activate` 激活环境。

## 3. 安装第三方工具

### 仅输出 `.fig`

```powershell
python scripts/bootstrap.py --profile fig
ui-rebuilder doctor
```

该命令会：

1. 按 `third_party/tools.lock.json` 获取固定版本的 OpenPencil；
2. 应用经过审查的 Windows 兼容补丁；
3. 将 Bun 复制到 `third_party/.runtimes/bun/`；
4. 还原依赖并构建 OpenPencil 包。

### 完整恢复和受控生成环境

```powershell
python scripts/bootstrap.py --profile all --install-comfy-python
```

工具源码、自定义节点和 Python 环境都会写入 `third_party/`。如果 PyTorch 需要特定 CUDA 源，显式传入：

```powershell
python scripts/bootstrap.py --profile all --install-comfy-python `
  --torch-index-url https://download.pytorch.org/whl/cu129
```

不要照抄 CUDA 版本；应按本机驱动和显卡选择。

### 使用已有本地安装

Windows 用户可以把已测试的 OpenPencil、ComfyUI、便携 Python 和模型复制进项目：

```powershell
.\scripts\import_local_toolchain.ps1 `
  -OpenPencilSource (Resolve-Path '..\open-pencil') `
  -ComfyUiSource (Resolve-Path '..\ComfyUI\ComfyUI') `
  -ComfyPythonSource (Resolve-Path '..\ComfyUI\python') `
  -CheckpointSource (Resolve-Path '..\model-downloads')
```

复制脚本不会删除或修改源安装，并会过滤输入、输出、用户数据、缓存、日志和机器相关路径。

## 4. 安装模型

模型不随仓库发布。根据 [模型清单](../third_party/models.lock.json) 下载后放到指定位置，例如：

```text
third_party/comfyui/models/checkpoints/
third_party/comfyui/models/controlnet/
third_party/comfyui/models/ipadapter/
third_party/comfyui/models/clip_vision/
third_party/comfyui/models/sam2/
```

验证文件：

```powershell
python scripts/verify_models.py --profile recovery
python scripts/verify_models.py --profile generation
```

`valid: true` 只表示文件存在且满足清单校验，不代表已经取得模型使用或分发许可。

## 5. 运行最小示例

```powershell
python examples/minimal/create_reference.py
ui-rebuilder build examples/minimal/minimal.job.yaml --output Output/minimal --force
ui-rebuilder validate Output/minimal
```

预期结果：

- `validate` 返回 `valid: true`；
- `Output/minimal/Design/` 下存在 `.fig`；
- `Reports/OpenPencil/fig-completeness.json` 中 `structurallyComplete` 为 `true`；
- `Previews/` 包含五页预览和资产总览。

## 6. 创建自己的任务

建议为每张原稿建立独立目录：

```text
jobs/training/
  reference.png
  style.json
  training.job.yaml
  assets/               # 可选的外部提取/修复素材
```

最小任务结构：

```yaml
schemaVersion: 1
id: training-screen
name: Training screen
reference:
  path: reference.png
styleProfile: style.json
layout:
  kind: inline
  screen:
    name: Screen/Training
    type: frame
    bounds: [0, 0, 1920, 1080]
  nodes:
    - name: Panel/Main
      type: frame
      parent: Screen/Training
      bounds: [320, 180, 1280, 720]
outputs: [package, openpencil-fig]
```

`bounds` 格式为 `[x, y, width, height]`。顶层节点使用屏幕坐标，子节点最终会转换为相对父节点坐标。

### 声明图片资产

从原稿裁切：

```yaml
assets:
  - id: main_panel_shell
    sourceBox: [320, 180, 1280, 720]
    method: extracted
    role: panel-shell
    targetNode: Panel/Main
    targetSize: [1280, 720]
    scaling: nine-slice
    borderLTRB: [48, 48, 48, 48]
```

使用外部透明素材：

```yaml
assets:
  - id: primary_button
    sourcePath: assets/primary-button.png
    method: repaired
    targetNode: Button/Primary
    trimTransparent: true
    alphaRequired: true
    scaling: uniform
```

可用的 `method`：`extracted`、`repaired`、`generated`、`vector`、`runtime`。可用的缩放方式：`none`、`uniform`、`nine-slice`、`tile`。

### 文字回退

无头环境无法保证拥有消费项目字体。需要稳定中文预览时：

```yaml
textFallback:
  enabled: true
  fontPath: fonts/ConsumerFont.ttf
  fontFamily: Consumer Font
  hideEditableTextInPreview: true
```

字体文件属于消费项目，不应提交到 UI Rebuilder 公共仓库。

## 7. 构建和验证

```powershell
ui-rebuilder build jobs/training/training.job.yaml --output Output/training
ui-rebuilder validate Output/training
```

常用选项：

- `--force`：允许覆盖已有非空输出目录；
- `--skip-openpencil`：只输出 UIIR、资产和基础预览；
- `--skip-openpencil-preview`：生成 `.fig`，但跳过页面 PNG 导出；
- `--openpencil-repo PATH`：临时使用显式 OpenPencil 仓库。

## 8. 启动 ComfyUI

```powershell
python scripts/run_comfyui.py
```

默认监听 `http://127.0.0.1:8190`。将模板需要的结构图和风格参考放入：

```text
third_party/comfyui/input/ui-rebuilder/
```

然后复制并修改工作流模板，再入队：

```powershell
python scripts/queue_comfyui_workflow.py `
  workflows/comfyui/controlled-ui-ornament.template.api.json
```

受控生成结果仍是候选资产，必须记录模型、种子、输入哈希并经过人工选择，不能静默覆盖提取资产。

## 9. 常见问题

### `doctor` 找不到 OpenPencil

先运行 `python scripts/bootstrap.py --profile fig`。也可以设置 `UI_REBUILDER_OPENPENCIL_ROOT` 或使用 `--openpencil-repo`。

### 构建提示输出目录非空

选择新的输出目录，或在确认旧输出可被替换后添加 `--force`。

### `.fig` 成功但视觉仍有差异

结构完整性只检查页面、层级、几何、嵌图和组件契约。继续检查 `Previews/`、原稿叠加结果和 `Reports/OpenPencil/`，再进行人工视觉验收。

### ComfyUI 找不到模型

确认文件名和目录与 `models.lock.json` 完全一致，然后运行 `scripts/verify_models.py`。不要通过外部绝对路径绕过项目模型目录。
