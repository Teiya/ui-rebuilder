# Third-party notices

UI Rebuilder does not redistribute the source or model files listed below. Its bootstrap process downloads them from their upstream publishers into the Git-ignored `third_party/` workspace. Each downloaded project remains governed by its own license.

## Required for `.fig` output

- [OpenPencil](https://github.com/open-pencil/open-pencil), pinned in `third_party/tools.lock.json`, MIT License.
- [Bun](https://github.com/oven-sh/bun), required to build the pinned OpenPencil checkout. Bun and its bundled components have their own license notices.

## Optional recovery and controlled generation

- [ComfyUI](https://github.com/Comfy-Org/ComfyUI), GPL-3.0.
- The ComfyUI custom nodes listed in `third_party/tools.lock.json`. Their upstream license files must be reviewed before redistribution or modification.
- The model weights listed in `third_party/models.lock.json`. Model licenses are independent from the code licenses; some prohibit or condition particular uses.

## Evaluation-only tools

- [BiRefNet](https://github.com/ZhengPeng7/BiRefNet), [UIED](https://github.com/MulongXie/UIED), and [OmniParser](https://github.com/microsoft/OmniParser) are locked under the `evaluation` profile to reproduce earlier UI-decomposition comparisons. They are not loaded by the selected production pipeline. OmniParser's model licenses differ from its repository license and must be reviewed separately.

Python dependencies declared in `pyproject.toml` are installed from their package indexes and are not vendored. Generated output can also contain consumer-owned fonts, artwork, or model output; publishing this repository does not grant rights to those consumer inputs or outputs.

This notice is an inventory, not legal advice and not a replacement for upstream license text.
