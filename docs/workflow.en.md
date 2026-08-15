# UI Reconstruction Workflow

[简体中文](workflow.md) | [English](workflow.en.md)

UI Rebuilder does not aim to repaint a screenshot into another similar screenshot. Its goal is to migrate a flattened reference into a UI system that can be inspected, edited, reused, and implemented.

## 1. Input contract

Every reconstruction needs at least:

1. a flattened reference image;
2. a style profile;
3. a layout description or layout authority;
4. the requested output types.

Gameplay, interaction states, and information priority must be established by the consumer project. The pipeline does not invent business rules from pixels.

## 2. Spec: define what the screen does

Before processing art, define the screen goal, primary action, information hierarchy, default/selected/locked/disabled/failure states, dynamic text and values, longest localized text, and accessibility requirements.

These facts belong to the consumer UX contract and are not hardcoded in the reusable pipeline.

## 3. Inventory and catalog: identify reusable material

`inventory` records what already exists in references or a consumer project. `catalog` turns credible panels, buttons, backgrounds, and tips into searchable templates.

The initial portable families are `button`, `popup`, `background`, and `tip`. Weak labels are acceptable when they remain explicit and inspectable.

## 4. Layout: build semantic hierarchy

Layout can come from:

- `inline`: screen and nodes declared directly in the job;
- `layout-authority`: nodes and geometry imported from another tool.

Hierarchy follows semantic ownership, not only screenshot coordinates. A success ring, its caption, and its percentage should share a component parent; a button label should be a child of its button. This keeps alignment, scaling, and state changes maintainable.

UIIR stores node type, semantic name, parentage, relative and reference geometry, dynamic-content flags, style, constraints, asset bindings, provenance, confidence, and review requirements.

## 5. Assets: extract, repair, or generate

Use a fixed priority:

| Order | Method | Use when | Constraint |
| --- | --- | --- | --- |
| 1 | `extracted` | reliable pixels exist in the reference | retain the source hash and crop box |
| 2 | `repaired` | text occludes an element, edges are contaminated, or alpha is missing | prefer deterministic operations and record the repair source |
| 3 | `generated` | no complete source exists or matching style material must be added | fix model, seed, structure/style conditions, and require review |
| 4 | `vector` | simple geometry can be reconstructed accurately | keep it parametric and editable |
| 5 | `runtime` | values, progress, state, or gameplay-driven graphics | do not bake it into static art |

Processing rules:

- scale circles, portraits, and badges uniformly;
- use nine-slice only for stretchable panels and bars with explicit protected borders;
- uniformly scale buttons, icons, and illustrations with integral composition;
- keep text, numbers, lock states, and progress fills separate;
- audit alpha, dark fringes, color contamination, and background dependencies;
- retain generated and extracted candidates separately rather than silently replacing one with the other.

## 6. Recipe: describe composition

A recipe connects layout and catalog material. It records the chosen component template, slot bindings, text/state payload, and unresolved assumptions. A recipe is not a Unity Prefab; runtime composition belongs to the consumer-specific assembly layer.

## 7. OpenPencil: generate the five-page design source

| Page | Content |
| --- | --- |
| `00_Foundations` | color, spacing, typography, radius, and stroke foundations |
| `10_Wireframe` | hierarchy and layout without final art dependency |
| `20_Visual` | primary screen assembled from real components and assets |
| `30_States` | selected, locked, disabled, failure, and other states |
| `90_Export` | reusable Components, asset dimensions, and export area |

Static art is embedded in `.fig`; dynamic copy remains native Text. The export page owns Components, while visual and state pages use Instances.

## 8. Automated quality gate

The build checks that:

- all five pages exist and contain content;
- every UIIR node appears in wireframe and visual output;
- every manifest asset is embedded and represented by an export Component;
- hierarchy and parent-relative geometry conform;
- export Component dimensions match the asset manifest;
- typography, color, spacing, overlap, and lint reports were produced.

`complete-fig-pending-visual-approval` means that this structural gate passed. It is not visual approval.

## 9. Human visual approval

Review source overlays, critical component proportions and visual centers, color and alpha edges, screen states and longest text, and scaling at target resolutions.

Fix the responsible layer: layout issues in UIIR/recipe, raster issues in extraction or repair, style issues in Foundations, and business-rule issues in the consumer UX contract.

## 10. Runtime handoff

After approval, the consumer project uses UIIR, the asset manifest, `.fig`, and state pages to build the runtime hierarchy. Revalidate anchors, localization, state transitions, import settings, nine-slice borders, and design/preview/runtime conformance.

UI Rebuilder currently produces engine-neutral handoff artifacts. Automatic Unity uGUI Prefab assembly remains a future adapter.
