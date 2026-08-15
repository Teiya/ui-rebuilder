# UI Rebuilder collaboration notes

- Keep the core project-agnostic. Do not hardcode consumer project names, art styles, absolute paths, Unity folders, or model locations.
- Treat `UIIR` as the canonical reconstruction format. `.fig`, PNG/SVG packages, and engine recipes are derived exports.
- Keep `spec`, `inventory/catalog`, `recipe`, and `assembly` separate.
- Prefer extraction and deterministic repair over generation. Generated pixels must carry provenance, model identity, seed, and review status.
- Model weights, fonts, private screenshots, and consumer project art do not belong in this repository.
- Use synthetic or redistributable fixtures in tests. Private integration jobs stay in the consumer project.
- OpenPencil integration must use a pinned consumer toolchain when one is supplied. A successful CLI exit is not visual approval.

