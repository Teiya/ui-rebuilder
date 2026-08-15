# Getting Started

[简体中文](getting-started.md) | [English](getting-started.en.md)

This guide covers installation from a clean checkout, reconstruction job authoring, `.fig` output, and the optional ComfyUI toolchain.

## 1. Requirements

- Windows, macOS, or Linux;
- Python 3.11+;
- Git;
- Bun 1.3.5 for the initial OpenPencil restore and build.

ComfyUI is optional. It requires a GPU driver compatible with the selected PyTorch build. UIIR generation, deterministic image processing, and `.fig` output do not require a GPU.

## 2. Install the core package

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

On Linux/macOS, activate the environment with `source .venv/bin/activate`.

## 3. Install third-party tools

### `.fig` output only

```powershell
python scripts/bootstrap.py --profile fig
ui-rebuilder doctor
```

This command checks out the pinned OpenPencil revision, applies reviewed compatibility patches, copies Bun into `third_party/.runtimes/bun/`, restores dependencies, and builds the OpenPencil packages.

### Full recovery and controlled-generation environment

```powershell
python scripts/bootstrap.py --profile all --install-comfy-python
```

Tool source, custom nodes, and the Python environment are installed below `third_party/`. If PyTorch requires a specific accelerator index, select it explicitly:

```powershell
python scripts/bootstrap.py --profile all --install-comfy-python `
  --torch-index-url https://download.pytorch.org/whl/cu129
```

Do not copy this CUDA version blindly; select the build that matches the target machine.

### Import an existing local installation

Windows users can copy a previously tested OpenPencil, ComfyUI, portable Python, and checkpoint setup into the project:

```powershell
.\scripts\import_local_toolchain.ps1 `
  -OpenPencilSource (Resolve-Path '..\open-pencil') `
  -ComfyUiSource (Resolve-Path '..\ComfyUI\ComfyUI') `
  -ComfyPythonSource (Resolve-Path '..\ComfyUI\python') `
  -CheckpointSource (Resolve-Path '..\model-downloads')
```

The import script does not delete or modify the source installation. It excludes inputs, outputs, user data, caches, logs, and machine-specific path configuration.

## 4. Install model weights

Model weights are not distributed with the repository. Download them from the sources in the [model manifest](../third_party/models.lock.json) and place them under the declared paths, such as:

```text
third_party/comfyui/models/checkpoints/
third_party/comfyui/models/controlnet/
third_party/comfyui/models/ipadapter/
third_party/comfyui/models/clip_vision/
third_party/comfyui/models/sam2/
```

Verify the installation:

```powershell
python scripts/verify_models.py --profile recovery
python scripts/verify_models.py --profile generation
```

`valid: true` means that the files satisfy the manifest checks. It does not grant usage or redistribution rights.

## 5. Run the minimal example

```powershell
python examples/minimal/create_reference.py
ui-rebuilder build examples/minimal/minimal.job.yaml --output Output/minimal --force
ui-rebuilder validate Output/minimal
```

Expected results:

- validation reports `valid: true`;
- `Output/minimal/Design/` contains a `.fig` file;
- `Reports/OpenPencil/fig-completeness.json` reports `structurallyComplete: true`;
- `Previews/` contains five page previews and an asset contact sheet.

## 6. Create a reconstruction job

Use a separate directory for each reference:

```text
jobs/training/
  reference.png
  style.json
  training.job.yaml
  assets/               # optional extracted or repaired source assets
```

Minimal job:

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

Bounds use `[x, y, width, height]`. Screen-level input is absolute; child geometry is normalized to parent-relative coordinates in UIIR.

### Declare a raster asset

Crop from the reference:

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

Use an external transparent asset:

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

Supported methods are `extracted`, `repaired`, `generated`, `vector`, and `runtime`. Supported scaling modes are `none`, `uniform`, `nine-slice`, and `tile`.

### Font fallback

For deterministic CJK previews in headless environments:

```yaml
textFallback:
  enabled: true
  fontPath: fonts/ConsumerFont.ttf
  fontFamily: Consumer Font
  hideEditableTextInPreview: true
```

Consumer fonts remain consumer-owned and should not be added to this public repository.

## 7. Build and validate

```powershell
ui-rebuilder build jobs/training/training.job.yaml --output Output/training
ui-rebuilder validate Output/training
```

Useful options:

- `--force`: replace a non-empty output directory;
- `--skip-openpencil`: emit UIIR, assets, and base previews only;
- `--skip-openpencil-preview`: create `.fig` without exporting page PNGs;
- `--openpencil-repo PATH`: use an explicit OpenPencil checkout for this run.

## 8. Start ComfyUI

```powershell
python scripts/run_comfyui.py
```

The default endpoint is `http://127.0.0.1:8190`. Put template inputs under:

```text
third_party/comfyui/input/ui-rebuilder/
```

Copy and edit the API workflow template, then queue it:

```powershell
python scripts/queue_comfyui_workflow.py `
  workflows/comfyui/controlled-ui-ornament.template.api.json
```

A controlled-generation result remains a candidate. Record its model, seed, and input hashes, and require human review before selection.

## 9. Troubleshooting

### `doctor` cannot find OpenPencil

Run `python scripts/bootstrap.py --profile fig`. Alternatively set `UI_REBUILDER_OPENPENCIL_ROOT` or pass `--openpencil-repo`.

### The output directory is not empty

Choose another output directory or add `--force` after confirming that the existing output may be replaced.

### The `.fig` is valid but still looks different

Structural validation checks pages, hierarchy, geometry, embedded assets, and components. Inspect `Previews/`, source overlays, and `Reports/OpenPencil/`, then perform human visual review.

### ComfyUI cannot find a model

Match the filename and location in `models.lock.json`, then run `scripts/verify_models.py`. Do not bypass the project model directory with machine-specific absolute paths.
