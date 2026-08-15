# Downloaded tool workspace

This directory is the installation target for external UI workflow tools. Downloaded source, virtual environments, model weights, caches, and generated data are ignored by Git.

The default self-contained local layout is:

```text
third_party/
  open-pencil/
  .runtimes/bun/             # project-local OpenPencil runtime
  comfyui/
    custom_nodes/
    models/
  .runtimes/comfyui-python/   # copied portable runtime, when available
  .venvs/comfyui/             # bootstrap-created alternative
  birefnet/                   # evaluation profile
  uied/                       # evaluation profile
  omniparser/                 # evaluation profile
```

All paths are resolved from the UI Rebuilder repository root. No downloaded tool needs to remain in a sibling directory after local setup.

Committed files are limited to:

- `tools.lock.json`: upstream repositories, immutable revisions, profiles, licenses, and build commands;
- `models.lock.json`: expected model filenames, sources, sizes, hashes, and license-review status;
- `patches/`: small reviewed compatibility patches applied after checkout.

## Profiles

| Profile | Installs | Purpose |
| --- | --- | --- |
| `fig` | OpenPencil | `.fig` construction, inspection, lint, and export |
| `recovery` | ComfyUI, SAM2, LaMa, LayerStyle | segmentation, masking, removal, and deterministic recovery |
| `generation` | ComfyUI, ControlNet Aux, IPAdapter Plus, LayerDiffuse, upscale/utility nodes | controlled reconstruction candidates |
| `operator` | ComfyUI Manager | optional interactive node management |
| `all` | every production tool and node above | full selected production workspace |
| `evaluation` | BiRefNet, UIED, OmniParser | reproduce earlier decomposition comparisons; not part of the selected production runtime |

## Import an existing local toolchain

For local development, copy the already-tested OpenPencil and ComfyUI installation into this repository instead of continuing to reference external paths:

```powershell
.\scripts\import_local_toolchain.ps1 `
  -OpenPencilSource (Resolve-Path '..\open-pencil') `
  -ComfyUiSource (Resolve-Path '..\ComfyUI\ComfyUI') `
  -ComfyPythonSource (Resolve-Path '..\ComfyUI\python') `
  -CheckpointSource (Resolve-Path '..\model-downloads')
```

Adjust the four source paths to the existing installation. The script copies only the selected ComfyUI nodes and models, excludes inputs, outputs, user data, caches, logs, and machine-specific path configuration, then restores and rebuilds OpenPencil inside `third_party/open-pencil`. It does not delete or modify the source installation.

The imported files remain local because `.gitignore` excludes every downloaded child of `third_party/`. Only this README, the two lock manifests, and reviewed patches can be committed.

Install source and build the `.fig` toolchain:

```powershell
python scripts/bootstrap.py --profile fig
```

Install the complete ComfyUI source/node set and a local Python environment:

```powershell
python scripts/bootstrap.py --profile all --install-comfy-python
```

Add `--profile evaluation` to also download the comparison-only UIED, OmniParser, and BiRefNet checkouts.

Select a PyTorch wheel index explicitly when your CUDA/ROCm environment requires it. The bootstrap script does not guess a GPU ABI.

Models are intentionally manual because several require license acceptance or account access and total many gigabytes. Download only the models needed by your profile, place them at the paths in `models.lock.json`, and verify them:

```powershell
python scripts/verify_models.py --profile recovery --hash
python scripts/verify_models.py --profile generation --hash
```

Never commit the downloaded directories. If a tool must be upgraded, update its immutable revision, review its license and changelog, refresh the patch, then run the full UI Rebuilder test and `.fig` validation suite.

The evaluation tools intentionally use their own upstream environment instructions: their Python/model requirements conflict with one another and they were not selected for the final reconstruction path. ImageGen is a hosted capability rather than a downloadable repository; its outputs must be registered through provenance instead of being installed here. The useful deterministic checks from the previously evaluated `image-to-code` skill have been implemented directly in UI Rebuilder, so that skill is not a runtime dependency.
