# Migration plan

## M0: contracts

- portable job, style-profile, UIIR, and manifest schemas;
- source hashing and provenance;
- package validator;
- synthetic tests.

## M1: editable structure

- inline and existing layout-authority import;
- hierarchy and parent-relative bounds;
- OpenPencil `.fig` exporter;
- overlay and OpenPencil diagnostic reports.

## M2: deterministic asset recovery

- implemented: external source snapshots, reference crops and source hashes;
- implemented: transparent trim, uniform contain, nine-slice, tile and target-size processing;
- implemented: Alpha checks, checkerboard contact sheet, UIIR binding and `.fig` image embedding;
- pending: automatic alpha/matting, geometry cleanup and LaMa adapter execution;
- pending: light/dark edge previews and automated chroma-fringe audit;
- provenance remains explicit as `extracted`, `repaired`, `generated`, `vector`, or `runtime`.

## M3: controlled generation

- ComfyUI and ImageGen adapters;
- reusable workflow templates and parameter scans;
- model/seed/hash records;
- candidate scoring without silent replacement of extracted pixels.

## M4: catalog and states

- implemented: manifest assets become native `90_Export` Components and bound visual assets become Instances;
- implemented: consumer-declared action and level-marker assets populate `30_States`;
- implemented: deterministic consumer-font preview fallbacks coexist with editable Text nodes;
- pending: remote consumer component catalog retrieval and native Variant grouping;
- pending: automatic synthesis of default, empty, selected, locked, failure, maximum-content, and longest-localized-text cases when they are absent from the job.

## M5: engine recipes

- engine-neutral anchor/layout/scaling recipe;
- optional Unity uGUI adapter maintained outside the portable core;
- three-way design/preview/runtime acceptance.

Private game art remains in the consumer repository. Integration tests invoke this repository by path and write generated diagnostics to consumer-owned temporary directories.
