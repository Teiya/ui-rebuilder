from __future__ import annotations

import json
from typing import Any


def render_openpencil_script(
    uiir: dict[str, Any],
    style_profile: dict[str, Any],
    embedded_images: dict[str, str] | None = None,
    asset_catalog: list[dict[str, Any]] | None = None,
) -> str:
    data = json.dumps(uiir, ensure_ascii=False)
    profile = json.dumps(style_profile, ensure_ascii=False)
    images = json.dumps(embedded_images or {}, ensure_ascii=False)
    assets = json.dumps(asset_catalog or [], ensure_ascii=False)
    return f'''const DATA = {data}
const PROFILE = {profile}
const IMAGE_DATA = {images}
const ASSET_CATALOG = {assets}
const CLEAR = []
const imageCache = new Map()

function decodeBase64(value) {{
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
  const clean = String(value || "").replace(/=+$/, "")
  const output = new Uint8Array(Math.floor(clean.length * 3 / 4))
  let offset = 0
  for (let index = 0; index < clean.length; index += 4) {{
    const a = alphabet.indexOf(clean[index])
    const b = alphabet.indexOf(clean[index + 1])
    const c = index + 2 < clean.length ? alphabet.indexOf(clean[index + 2]) : 0
    const d = index + 3 < clean.length ? alphabet.indexOf(clean[index + 3]) : 0
    const value24 = (a << 18) | (b << 12) | (c << 6) | d
    if (offset < output.length) output[offset++] = (value24 >> 16) & 255
    if (offset < output.length) output[offset++] = (value24 >> 8) & 255
    if (offset < output.length) output[offset++] = value24 & 255
  }}
  return output
}}

function imagePaint(asset) {{
  const encoded = IMAGE_DATA[asset.id]
  if (!encoded) return null
  let image = imageCache.get(asset.id)
  if (!image) {{
    image = figma.createImage(decodeBase64(encoded))
    imageCache.set(asset.id, image)
  }}
  return [{{ type: "IMAGE", imageHash: image.hash, scaleMode: "FIT", opacity: asset.opacity ?? 1 }}]
}}

function colorParts(value) {{
  const raw = String(value || "#000000").replace("#", "")
  const rgb = raw.slice(0, 6)
  const opacity = raw.length === 8 ? parseInt(raw.slice(6, 8), 16) / 255 : 1
  return {{ color: {{ r: parseInt(rgb.slice(0, 2), 16) / 255, g: parseInt(rgb.slice(2, 4), 16) / 255, b: parseInt(rgb.slice(4, 6), 16) / 255 }}, opacity }}
}}

function paint(value, opacity = 1) {{
  if (!value) return CLEAR
  const parsed = colorParts(value)
  return [{{ type: "SOLID", color: parsed.color, opacity: parsed.opacity * opacity }}]
}}

function applyStyle(node, style, type) {{
  style = style || {{}}
  if ("fills" in node) node.fills = style.fill ? paint(style.fill, style.opacity ?? 1) : CLEAR
  if ("strokes" in node) node.strokes = style.stroke ? paint(style.stroke, style.opacity ?? 1) : CLEAR
  if ("strokeWeight" in node) node.strokeWeight = style.strokeWidth ?? 1
  if ("cornerRadius" in node && style.cornerRadius !== undefined) node.cornerRadius = style.cornerRadius
  if (type === "text") {{
    node.fontName = {{ family: style.fontFamily || "Inter", style: "Regular" }}
    node.fontSize = style.fontSize || 12
    node.fills = paint(style.textColor || "#333333", style.opacity ?? 1)
  }}
}}

const parentIds = new Set(DATA.pages.flatMap(page => page.nodes.map(node => node.parent).filter(Boolean)))
const assetComponents = new Map()

function makeText(name, characters, size = 14) {{
  const node = figma.createText()
  node.name = name
  node.fontName = {{ family: "Inter", style: "Regular" }}
  node.fontSize = size
  node.characters = characters
  node.fills = paint(colors?.["text.primary"] || "#34342C")
  return node
}}

function createNode(spec, mode = "visual") {{
  let node
  const assetComponent = mode === "visual" && spec.asset ? assetComponents.get(spec.asset.id) : null
  const leafAssetInstance = assetComponent && !parentIds.has(spec.id)
  if (leafAssetInstance) node = assetComponent.createInstance()
  else if (spec.type === "text") node = figma.createText()
  else if (spec.type === "ellipse") node = figma.createEllipse()
  else if (spec.type === "rectangle" || spec.type === "image") node = figma.createRectangle()
  else if (spec.type === "component") node = figma.createComponent()
  else node = figma.createFrame()
  node.name = mode === "wireframe" ? `Wireframe/${{spec.name}}` : spec.name
  if (spec.type === "text") {{
    if (mode === "wireframe") {{
      applyStyle(node, {{ ...spec.style, textColor: "#60656A", fontFamily: "Inter", fontSize: 12 }}, spec.type)
      node.characters = spec.name.split("/").at(-1) || spec.id
    }} else {{
      applyStyle(node, spec.style, spec.type)
      node.characters = spec.text || ""
    }}
    node.textAutoResize = "NONE"
    node.textAlignVertical = "CENTER"
  }} else {{
    if (mode === "wireframe") {{
      if ("fills" in node) node.fills = spec.parent ? CLEAR : paint("#F5F6F7")
      if ("strokes" in node) node.strokes = spec.parent ? paint("#8B949B", 0.7) : paint("#4B5358")
      if ("strokeWeight" in node) node.strokeWeight = spec.parent ? 1 : 2
    }} else if (!leafAssetInstance) {{
      applyStyle(node, spec.style, spec.type)
      if (spec.asset && "fills" in node) {{
        node.fills = CLEAR
        if ("strokes" in node) node.strokes = CLEAR
        if ("cornerRadius" in node) node.cornerRadius = 0
      }}
    }}
    if ("clipsContent" in node) node.clipsContent = false
    if ("layoutMode" in node && ["HORIZONTAL", "VERTICAL"].includes(spec.layout?.mode)) {{
      node.layoutMode = spec.layout.mode
      node.primaryAxisSizingMode = "FIXED"
      node.counterAxisSizingMode = "FIXED"
    }}
  }}
  if (node.setPluginData) {{
    node.setPluginData("uiRebuilderId", spec.id)
    node.setPluginData("uiRebuilderType", spec.type)
    node.setPluginData("uiRebuilderProvenance", JSON.stringify(spec.provenance || {{}}))
    if (spec.asset) node.setPluginData("uiRebuilderAsset", JSON.stringify(spec.asset))
  }}
  return node
}}

function positionNode(node, spec, parent) {{
  if (parent.type !== "PAGE" && parent.layoutMode && parent.layoutMode !== "NONE") node.layoutPositioning = "ABSOLUTE"
  const width = Math.max(1, spec.bounds[2])
  const height = Math.max(1, spec.bounds[3])
  node.resize(width, height)
  node.x = spec.bounds[0]
  node.y = spec.bounds[1]
}}

function attachAssetBackground(node, spec) {{
  if (!spec.asset || !parentIds.has(spec.id)) return
  const component = assetComponents.get(spec.asset.id)
  if (!component) return
  const background = component.createInstance()
  background.name = `AssetInstance/${{spec.asset.id}}/Background`
  node.appendChild(background)
  if (node.layoutMode && node.layoutMode !== "NONE") background.layoutPositioning = "ABSOLUTE"
  background.resize(Math.max(1, spec.bounds[2]), Math.max(1, spec.bounds[3]))
  background.x = 0
  background.y = 0
  background.locked = true
  background.setPluginData("uiRebuilderRole", "visual-background")
}}

function attachTextFallback(parent, editableText, spec) {{
  const fallback = spec.textFallback
  if (!fallback || !IMAGE_DATA[fallback.id]) return
  const preview = figma.createRectangle()
  preview.name = `PreviewText/${{spec.name}}`
  parent.appendChild(preview)
  if (parent.type !== "PAGE" && parent.layoutMode && parent.layoutMode !== "NONE") preview.layoutPositioning = "ABSOLUTE"
  preview.resize(Math.max(1, spec.bounds[2]), Math.max(1, spec.bounds[3]))
  preview.x = spec.bounds[0]
  preview.y = spec.bounds[1]
  preview.fills = imagePaint(fallback) || CLEAR
  preview.strokes = CLEAR
  preview.locked = true
  preview.setPluginData("uiRebuilderEditableTextId", spec.id)
  if (fallback.hideEditableTextInPreview) editableText.visible = false
}}

const standardPages = ["00_Foundations", "10_Wireframe", "20_Visual", "30_States", "90_Export"]
for (const page of [...figma.root.children].slice(1)) page.remove()
const pageMap = new Map()
for (const [index, name] of standardPages.entries()) {{
  const page = index === 0 ? figma.currentPage : figma.createPage()
  for (const child of [...page.children]) child.remove()
  page.name = name
  pageMap.set(name, page)
}}

const colors = PROFILE.tokens?.colors || {{}}
const spacing = PROFILE.tokens?.spacing || {{}}
if (figma.createVariableCollection && figma.createVariable) {{
  const colorCollection = figma.createVariableCollection("UIR/Color")
  for (const [name, value] of Object.entries(colors)) figma.createVariable(name, "COLOR", colorCollection.id, colorParts(value).color)
  const spacingCollection = figma.createVariableCollection("UIR/Spacing")
  for (const [name, value] of Object.entries(spacing)) figma.createVariable(name, "FLOAT", spacingCollection.id, value)
}}

const foundationPage = pageMap.get("00_Foundations")
const board = figma.createFrame()
board.name = `Foundations/${{PROFILE.id}}`
foundationPage.appendChild(board)
board.resize(1280, 720)
board.x = 40
board.y = 40
board.fills = paint(colors["surface.paper"] || colors.paper || "#F5F0E3")
const foundationTitle = makeText("Heading/Foundations", `UI Foundations · ${{PROFILE.id}}`, 24)
board.appendChild(foundationTitle)
foundationTitle.resize(1000, 40)
foundationTitle.x = 32
foundationTitle.y = 24
let tokenIndex = 0
for (const [name, value] of Object.entries(colors)) {{
  const column = tokenIndex % 5
  const row = Math.floor(tokenIndex / 5)
  const swatch = figma.createRectangle()
  swatch.name = `Token/Color/${{name}}`
  board.appendChild(swatch)
  swatch.resize(160, 72)
  swatch.x = 32 + column * 232
  swatch.y = 88 + row * 116
  swatch.fills = paint(value)
  const label = makeText(`Label/Color/${{name}}`, `${{name}}\n${{value}}`, 12)
  board.appendChild(label)
  label.resize(210, 40)
  label.x = swatch.x
  label.y = swatch.y + 76
  tokenIndex += 1
}}

const exportPage = pageMap.get("90_Export")
let exportX = 40
let exportY = 40
let exportRowHeight = 0
for (const asset of ASSET_CATALOG) {{
  const width = Math.max(1, asset.pixelSize?.[0] || 64)
  const height = Math.max(1, asset.pixelSize?.[1] || 64)
  if (exportX > 40 && exportX + width > 3200) {{
    exportX = 40
    exportY += exportRowHeight + 80
    exportRowHeight = 0
  }}
  const component = figma.createComponent()
  component.name = `Asset/${{asset.id}}/Runtime`
  exportPage.appendChild(component)
  component.resize(width, height)
  component.x = exportX
  component.y = exportY
  component.fills = imagePaint(asset) || CLEAR
  component.strokes = CLEAR
  component.cornerRadius = 0
  component.clipsContent = false
  component.setPluginData("uiRebuilderAsset", JSON.stringify(asset))
  assetComponents.set(asset.id, component)
  exportX += width + 80
  exportRowHeight = Math.max(exportRowHeight, height)
}}

for (const pageSpec of DATA.pages) {{
  const page = pageMap.get(pageSpec.name) || figma.createPage()
  page.name = pageSpec.name
  pageMap.set(pageSpec.name, page)
  const nodes = new Map()
  for (const spec of pageSpec.nodes) {{
    const parent = spec.parent ? nodes.get(spec.parent) : page
    if (!parent) throw new Error(`Missing parent ${{spec.parent}} for ${{spec.id}}`)
    const node = createNode(spec)
    parent.appendChild(node)
    positionNode(node, spec, parent)
    attachAssetBackground(node, spec)
    if (spec.type === "text") attachTextFallback(parent, node, spec)
    nodes.set(spec.id, node)
  }}
}}

const visualSpec = DATA.pages.find(page => page.name === "20_Visual") || DATA.pages[0]
const wireframePage = pageMap.get("10_Wireframe")
if (visualSpec) {{
  const nodes = new Map()
  for (const spec of visualSpec.nodes) {{
    const parent = spec.parent ? nodes.get(spec.parent) : wireframePage
    if (!parent) throw new Error(`Missing wireframe parent ${{spec.parent}} for ${{spec.id}}`)
    const node = createNode(spec, "wireframe")
    parent.appendChild(node)
    positionNode(node, spec, parent)
    nodes.set(spec.id, node)
  }}
}}

const statesPage = pageMap.get("30_States")
const statesTitle = makeText("Heading/States", "Reusable control and state assets", 22)
statesPage.appendChild(statesTitle)
statesTitle.resize(720, 40)
statesTitle.x = 40
statesTitle.y = 32
const stateAssets = ASSET_CATALOG.filter(asset =>
  /^state_/i.test(asset.id || "") || /(action-shell|level-marker)$/i.test(asset.role || "")
)
let stateX = 40
for (const asset of stateAssets) {{
  const component = assetComponents.get(asset.id)
  if (!component) continue
  const instance = component.createInstance()
  instance.name = `State/${{asset.id}}`
  statesPage.appendChild(instance)
  instance.x = stateX
  instance.y = 104
  const label = makeText(`Label/State/${{asset.id}}`, asset.id, 12)
  statesPage.appendChild(label)
  label.resize(Math.max(180, asset.pixelSize?.[0] || 64), 32)
  label.x = stateX
  label.y = 104 + (asset.pixelSize?.[1] || 64) + 12
  stateX += Math.max(220, (asset.pixelSize?.[0] || 64) + 80)
}}
if (stateAssets.length === 0) {{
  const note = makeText("Note/States/ConsumerOwned", "No explicit state assets were supplied by the consumer job.", 14)
  statesPage.appendChild(note)
  note.resize(720, 40)
  note.x = 40
  note.y = 104
}}

figma.currentPage = pageMap.get("20_Visual")
return {{ pages: standardPages, documentId: DATA.id }}
'''
