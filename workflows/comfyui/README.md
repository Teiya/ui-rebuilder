# ComfyUI workflow templates

These files use ComfyUI's API JSON format. They contain no consumer artwork, fonts, or private prompts.

`controlled-ui-ornament.template.api.json` demonstrates the controlled-generation branch used by UI Rebuilder:

1. a checkpoint provides the base visual prior;
2. Canny/Control-LoRA constrains geometry;
3. IPAdapter constrains style separately;
4. a fixed seed and explicit parameters make the candidate reproducible;
5. the result is still a candidate and never silently replaces extracted pixels.

Before queuing it:

- replace `YOUR_SDXL_CHECKPOINT.safetensors`;
- copy `structure-guide.png` and `style-reference.png` into `third_party/comfyui/input/ui-rebuilder/`;
- ensure the Control-LoRA, IPAdapter, and CLIP Vision files from `third_party/models.lock.json` are installed.

Start and queue:

```powershell
python scripts/run_comfyui.py
python scripts/queue_comfyui_workflow.py workflows/comfyui/controlled-ui-ornament.template.api.json
```

Project-specific workflows should be stored with their reconstruction job because prompts, masks, source images, model selection, and approval results belong to the consumer.
