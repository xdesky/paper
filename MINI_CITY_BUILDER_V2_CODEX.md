# MINI CITY BUILDER V2 — Implementation specification for Codex

## 0. Mission

Upgrade the existing Papercraft application from V1 (completed 3D gingerbread house models and printable PDFs, as reported by the project owner) into a commercial-ready modular Mini City Builder. Users build a gingerbread village digitally by dragging existing 3D models onto a grid, then print the corresponding physical paper models. Preserve all working V1 functionality. Do not assume any specific repository layout or framework until inspected.

**Product principle:** Build it digitally. Create it physically.

## 1. Instructions to Codex

- Inspect the repository, README, dependencies, routes, current model generation, PDF generation, data structures and existing tests before editing. Identify the actual source of truth for model geometry, textures, units and printable templates.
- Record findings and implementation plan in `docs/mini-city-v2-plan.md` (adapt paths to existing conventions). Then implement; do not stop at planning or mockups.
- Reuse the existing stack, design system, V1 assets and PDF engine. If Three.js or React Three Fiber already exists, reuse it. Introduce new dependencies only when necessary and document them.
- Add City Builder as a separate route or workspace, with navigation from V1 and back. Do not replace or rewrite the original editor. Keep migrations backward compatible and avoid destructive changes.
- Never fabricate missing geometry, PDF files, textures, asset dimensions or successful test results. Inventory missing data and implement clear error states. Use fixtures only in tests, explicitly labeled.
- Work in incremental, testable phases. Keep changes scoped; run the existing regression suite and build after each major phase. Do not deploy or modify production data without explicit approval.

## 2. Scope and user flow

1. Open **City Builder** from the existing app.
2. Start a new village or reopen a saved project.
3. Browse thumbnails of the actual V1 gingerbread houses in the asset library.
4. Drag a house onto a 3D ground grid, or click an asset then click a target cell.
5. Move, rotate in 90-degree increments, duplicate or delete houses. Add printable road/ground tiles if available or implemented and validated.
6. Orbit, pan, zoom and reset the camera; switch between isometric and top-down views.
7. Save automatically, reopen, undo/redo changes.
8. Open Print Preview showing selected/all printable objects, quantities, scale, paper format, page count and errors.
9. Export a combined PDF with the matching model templates, plus a city layout/assembly reference page.
10. Print at actual size, cut, fold, glue, and place the houses according to the layout.

### MVP non-goals

No traffic simulation, economy, NPCs, multiplayer, AI-generated arbitrary geometry, marketplace, subscription billing, or complete new asset collection. No unrestricted mesh scaling in MVP. No need to regenerate existing PDFs merely because a house is moved or rotated on the ground.

## 3. UI / UX specification

Use the existing V1 visual identity. Aim for a clean, neutral, modern creative application with subtle gradient accents, not a complex CAD tool. Desktop-first reference viewport: 1280 × 832; support smaller screens with collapsible library and inspector.

| Area | Specification |
|---|---|
| Top bar | Brand, V1/City Builder navigation, editable project name, save status, undo/redo, Print & Export primary CTA |
| Left rail | Compact 44–48 px category icons, if consistent with existing UI |
| Asset library | 190–230 px collapsible panel, search, category filters, small 3D thumbnails, asset name, printable availability |
| Main canvas | Remaining space; true interactive 3D, orthographic isometric camera by default, ground grid, soft shadows, selection outline, placement ghost |
| Inspector | Contextual floating panel or collapsible right panel; selected asset, dimensions, rotation, quantity, duplicate/delete, template status |
| Bottom/status | Object count, city footprint, export warnings, keyboard hints |
| Print dialog | Selected/all, exact page count, format, copies, model list, warnings, preview, export progress |

Do not use a persistent large inspector when nothing is selected. Keep the 3D canvas as large as possible. All buttons must work; no decorative fake controls. Include loading, empty, offline/error and no-printable-template states. English UI by default; use existing localization infrastructure if present. Accessible labels, keyboard focus and tooltips required.

## 4. Asset registry — reuse V1, never duplicate the source of truth

Create an adapter over the existing model/template registry or a manifest derived from verified V1 data. Each asset must refer to the same version of geometry and print template. Example conceptual schema (adapt naming to codebase):

```ts
interface CityAsset {
  id: string;
  revision: string;
  name: string;
  category: 'gingerbread-house' | 'road' | 'ground' | 'decor';
  thumbnailUrl?: string;
  modelRef: string; // existing GLB, procedural model or geometry reference
  templateRef?: string; // existing PDF or deterministic generator reference
  physicalSizeMm: { width: number; depth: number; height: number };
  footprintMm: { width: number; depth: number };
  pivot: 'bottom-center';
  allowedRotations: number[];
  supportedPaperFormats: string[];
  printStatus: 'ready' | 'unavailable' | 'invalid';
}
```

- Actual asset dimensions must be measured or retrieved from V1, not guessed from a screenshot.
- Normalize imported models to a bottom-center pivot and a consistent up-axis without changing physical scale. Record conversion from renderer units to millimeters.
- Prefer existing model components when assets are procedural. Do not convert everything to GLB unnecessarily.
- Load thumbnails efficiently and cache geometries/materials. Clone transforms per instance; avoid shared mutable materials when customization is introduced.
- If V1 model and PDF use different dimensions, mark asset invalid until resolved. Never silently resize PDF to fit the model.

## 5. City scene data and persistence

```ts
interface CityObject {
  id: string;
  assetId: string;
  assetRevision: string;
  xCell: number;
  zCell: number;
  rotationDeg: 0 | 90 | 180 | 270;
}
interface CityProject {
  schemaVersion: 1;
  id: string;
  name: string;
  grid: { columns: number; rows: number; cellSizeMm: number };
  objects: CityObject[];
  updatedAt: string;
}
```

Use integer cells for deterministic placement. Suggest an initial 8 × 8 or 10 × 10 grid, configurable up to a documented safe limit. Choose cell size based on actual V1 house footprints, initially proposing 100 mm only if compatible. Larger assets occupy multiple cells: ceil(width/cellSize) × ceil(depth/cellSize); swap axes for 90/270 degrees. Reserve rectangular occupancy conservatively. Set object pivot consistently at the center of its occupied footprint. All objects remain grounded at y=0 after accounting for model pivot.

Persist via the existing project storage if available; otherwise use IndexedDB/local storage with explicit local-only status, schema validation, autosave debounce and recovery from corrupted saves. Support project JSON export/import as backup. Validate asset references and bounds on import; preserve unresolved objects with warnings rather than silently replacing them. Do not include blobs or signed URL secrets in project JSON. Use existing authentication/ownership rules if backend storage exists.

## 6. Placement and 3D interaction

- Raycast pointer against the ground plane; convert world coordinates to cells using a single coordinate conversion module.
- Render a translucent placement ghost: valid/invalid indication, footprint outline, no collision with other objects or map boundaries.
- Drop commits exactly one command; invalid placement leaves scene unchanged. Escape cancels, R rotates preview, Delete removes selected object, Ctrl/Cmd+Z undo, Ctrl/Cmd+Shift+Z redo, Ctrl/Cmd+D duplicate (only when focus is not in text fields).
- Dragging an existing object temporarily excludes its own occupancy; invalid move rolls back. Prevent orbit and drag handlers from competing. Support click-to-place fallback and pointer/touch interaction.
- Selection by raycast; highlight only the selected instance. Ground grid and ghost must not intercept object selection unintentionally.
- Rotate around footprint center or maintain a documented anchor convention, then revalidate occupancy. Duplicate to nearest available valid cells; if none, show a message.
- Undo/redo covers placement, move, rotation, duplication and deletion; use bounded command history. Autosave after committed changes, not every pointer movement.
- Orthographic camera with orbit, pan, zoom, top-down and reset-to-fit. Grounded shadows, neutral background, pastel gingerbread visuals; preserve actual V1 model appearance.
- Aim for responsive interaction with 100 objects on a typical desktop; benchmark and report observed performance, not invented FPS. Dispose unused GPU resources. Avoid reloading assets on every state update.

## 7. Roads, ground and layout

Phase A: houses only, plus an unobtrusive non-printing editor grid. Phase B: add straight, corner, T-junction, crossroad and blank ground tiles using the same module dimensions. Optional auto-connect based on adjacent road cells. Road geometry/texture and PDF must use identical tile dimensions. A visual-only road must be clearly marked non-printable and excluded from printable output with a warning. Do not confuse editor grid with printable base.

Use a consistent module system across the village. No mandatory real-world architectural scale such as 1:64 unless V1 geometry supports it. City dimensions must be derived from physical model sizes and grid dimensions.

## 8. PDF export — critical requirement

### 8.1 Export pipeline

1. Validate project and selected objects against registry, revision, dimensions and print status.
2. Freeze a snapshot of the project at export start.
3. Group instances by asset ID + revision + print variant. Count quantities, preserving duplicate houses.
4. Resolve existing PDFs or invoke the existing V1 generator with the original geometry and supported paper format.
5. Merge source PDF pages in deterministic order, repeating complete page sets per physical copy. A house with 3 pages placed twice must contribute 6 pages, not 3.
6. Add a cover/inventory and city layout map with model IDs, orientation arrows, grid coordinates, physical dimensions and print instructions. Add existing assembly instructions if available; avoid duplicate guide pages only when safe and clearly indicated.
7. Return a valid downloadable PDF; optionally ZIP of individual PDFs in a later iteration.

### 8.2 Physical fidelity

- Do not rasterize source PDF templates unless absolutely required by the original workflow. Preserve vectors, textures, cut lines, fold lines, glue tabs, edge numbering, page boxes and physical dimensions.
- Do not apply fit-to-page, arbitrary scale or stretch while merging. Rotation in the city changes placement only, not the shape or scale of the model's printable template.
- Preserve V1 supported paper formats. Default to US Letter if available; A4 only when native template generation supports it. Do not label converted Letter PDFs as A4 without validated repagination. Reject incompatible mixed-format exports or clearly offer a supported resolution.
- Show actual source page counts (including cover/layout pages) before export when available. Estimates must be labeled as estimates and replaced by actual counts after preflight.
- Include instructions: print at 100% / Actual Size, disable Fit to Page. Add a 50 mm calibration ruler on a separate generated layout/guide page; never overlay existing templates without checking reserved areas.
- If a source PDF is missing, corrupted, mismatched or unsupported, identify affected objects and block full export. Offer an explicit printable-only export if implemented; never silently omit assets.
- For large exports, show progress, support cancellation where feasible and ensure failed downloads can be retried. Enforce a documented page/file-size limit to prevent browser/server exhaustion.

### 8.3 Layout map

Provide a top-down reference of the full city, numbered models and orientations. If the city exceeds one page, either use a clearly labeled reduced-scale overview (not for physical assembly base), or implement tiled true-scale ground pages with registration marks as a later feature. Do not present a scaled overview as a physical base. If printable road tiles exist, export their actual-size PDFs separately in the same job.

### 8.4 API boundaries

Reuse existing V1 endpoints and export utilities. If a server export endpoint is needed, propose `POST /api/city/export` with validated project snapshot, selected IDs and paper format; return PDF bytes or a job ID using existing conventions. Resolve asset references server-side from trusted registry, never fetch arbitrary client URLs or file paths. Apply ownership checks, safe file names, limits and proper error handling. If existing app is client-only, use a compatible PDF merge library rather than introducing an unnecessary backend.

## 9. Implementation phases

| Phase | Deliverable | Exit condition |
|---|---|---|
| 0 | Repository audit, V1 asset inventory and baseline tests | Actual asset/PDF relationships documented; baseline known |
| 1 | Separate City Builder route, shell, real 3D grid, V1 asset library | Existing houses render; V1 unchanged |
| 2 | Drag/drop, click placement, move, rotate, duplicate, delete, collision and history | All interactions work deterministically |
| 3 | Project persistence, reopen, JSON backup, camera controls | Refresh/reopen restores scene accurately |
| 4 | Preflight, PDF merge, quantity handling, layout guide | Downloadable correct-size PDF from actual V1 templates |
| 5 | Printable road/ground modules, if feasible; UI polish, performance, accessibility | Verified print assets only, or clearly non-printable preview |
| 6 | Regression, end-to-end testing and documentation | MVP acceptance checklist complete or blockers explicitly recorded |

Prioritize phases 0–4. If road modules are not ready, ship a functioning gingerbread village with houses first. Do not let optional features block core export.

## 10. Test plan and acceptance criteria

### Unit/integration

- Registry maps every supported V1 house to the correct revision and PDF.
- Grid conversion, rotated multi-cell footprints, overlap, boundaries and self-exclusion pass tests.
- Commands and undo/redo restore exact project state; invalid placement creates no history entry.
- Save/load/import round-trip preserves asset IDs, revision, positions, rotations and dimensions.
- Export grouping counts all copies; deterministic ordering; missing templates fail with descriptive errors.
- PDF merge preserves source page MediaBox/CropBox dimensions and source page content orientation; generated pages have correct dimensions. Verify with PDF parsing, not only screenshots.
- Imported project payloads with invalid sizes, IDs, coordinates or references are safely handled.

### End-to-end scenario (use actual V1 assets)

- Open V1, confirm existing house rendering and original PDF export still work.
- Open City Builder; place three houses including two instances of the same asset. Rotate one, move another, attempt an overlapping drop, undo/redo, duplicate and delete.
- Save, reload, verify exact scene state; switch top-down/isometric and zoom.
- Print preview shows correct asset quantities and supported paper format.
- Export full village; open the PDF and verify all expected template pages and layout guide. Compare geometry and template dimensions against V1 sources.
- Export selected object only and verify the page set.
- Simulate missing PDF and confirm actionable error rather than empty/silent output.
- Manually print at actual size, measure calibration ruler and assemble at least one instance of each newly supported asset before declaring physically validated. If no printer is available, document manual physical QA as pending; do not claim it passed.

## 11. Deliverables and final report

- Working City Builder integrated into the current repository (not a separate mockup).
- Asset adapter/registry, scene editor, storage, PDF export, tests and documentation.
- README instructions: run, build, test, add a V1 asset, create a village, export and print.
- A reproducible demo project containing actual V1 gingerbread houses; optional screenshot generated from running app.
- Final report: changed files, commands run, test results, implementation decisions, known limitations, physical QA status, and remaining tasks. Clearly distinguish completed and unverified functionality.

## 12. Future roadmap (do not implement before core MVP is stable)

V2.1: custom signs, color variants tied to print textures, additional gingerbread stores, auto-connected printable roads, tiled base export. V2.2: theme packs and premium asset entitlements, with server-side authorization. V3: miniature city collections beyond Christmas, sharing/remix and optional AI asset creation through validated geometry/unfolding pipeline.

**Definition of done:** A user can build a village using existing gingerbread houses, persist the project, and obtain a correct PDF containing the exact printable templates and quantities needed to reproduce it physically, without any regression in V1.
