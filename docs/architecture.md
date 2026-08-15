# Architecture

## Canonical flow

```text
reference image + style profile + job hints
  -> intake and hashing
  -> inventory/layout import
  -> UIIR
  -> deterministic asset crops
  -> recipe and manifest
  -> OpenPencil / preview / future engine exporters
  -> validation report
```

`UIIR` is the only canonical reconstruction structure. `.fig` and runtime recipes are derived artifacts.

## Data layers

1. `spec`: what the requested screen must communicate and which states exist.
2. `inventory`: weakly labelled source material and detected nodes.
3. `catalog`: reusable component candidates supplied by the consumer.
4. `recipe`: selected components, slots, text payload, and assumptions.
5. `UIIR`: concrete editable hierarchy, bounds, constraints, styles, assets, confidence, and provenance.
6. `assembly`: a consumer-owned engine implementation.

The portable `UiInventory` schemas cover inventory, catalog, and recipe. UI Rebuilder adds job, style-profile, UIIR, and reconstruction-manifest schemas.

## Adapter boundaries

- `OpenPencilAdapter`: converts UIIR to editable native nodes and writes tool diagnostics.
- `RecoveryAdapter`: future interface for LaMa, OpenCV inpaint, matting, or segmentation.
- `GenerationAdapter`: future interface for ImageGen, ComfyUI, or a project LoRA.
- `EngineRecipeExporter`: future semantic handoff; it must not directly own gameplay or runtime presenters.

Every generated or repaired asset must record method, source region, input hash, tool/model identity, seed when relevant, confidence, and review status.

## OpenPencil boundary

The independent repository discovers OpenPencil through an explicit path, `UI_REBUILDER_OPENPENCIL_ROOT`, the project-local `third_party/open-pencil` slot, a sibling repository, or a PATH installation. `third_party/tools.lock.json` pins the public default revision and reviewed compatibility patches; a consumer can still supply and validate a different explicit toolchain.

The exporter creates native frames, rectangles, ellipses, editable text, Components, and Instances. Consumer-owned raster files are copied into the auditable package, processed deterministically, bound through UIIR, and embedded as image fills in `.fig`. Dynamic text, values, progress and state overlays remain separate semantic nodes. When the consumer supplies a font, exact-size raster text previews are emitted beside hidden editable Text nodes so headless export remains readable without sacrificing editability.

OpenPencil is not the asset processor. Alpha trimming, uniform fitting, nine-slice and tiling happen before export so the `.fig` and engine recipes consume the same hashed raster output.

## Structural completion gate

The adapter writes five canonical pages: foundations, wireframe, visual, states, and export. `fig-completeness.json` blocks a successful build unless page population, UIIR coverage, embedded-image counts, geometry conformance, and export Component conformance all pass. Tool lint remains a separate diagnostic because its accessibility preset assumes Web/touch semantics that do not always apply to game decoration or asset-catalog nodes.

## Downloaded tool boundary

OpenPencil, ComfyUI, ComfyUI custom nodes, Python environments, and model weights live under the Git-ignored `third_party/` workspace after bootstrap. The repository commits only immutable source locks, model identity records, license/source links, and reviewed patches. ComfyUI is divided into recovery and controlled-generation profiles so `.fig` users do not need to install GPU dependencies.
