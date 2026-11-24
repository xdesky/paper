# Mini City Builder V2 implementation plan

## Repository audit

- Frontend: React 19, TypeScript, Vite, Three.js 0.180; account-aware studio in `frontend/src/main.tsx`.
- Backend: FastAPI with SQLite and owner-scoped sessions/projects in `backend/app.py` and `backend/accounts.py`.
- Canonical asset registry: `backend/template_catalog.py` (`TEMPLATES`, `BY_ID`, `CATALOG_VERSION`). Gingerbread house and miniature storefront dimensions are catalog millimeters; blocky characters are a separate model family and are excluded from this house-village MVP.
- Canonical house geometry/art: `backend/gingerbread.py` (`model`, `decorations`, `svg_art`, `generate`) and `backend/accessories.py` (`scene`). 3D panel vertices and artwork are generated from the same template records used by the PDF engine.
- Print source: `backend/worker.py` delegates house output to `backend/gingerbread.py`; it writes vector US Letter/A4 PDFs (`printable_us_letter.pdf` / `printable_a4.pdf`) and SVG pages. Existing PDF samples live under `output/`; runtime export will call the generator and cache its actual source PDF rather than infer or rescale a sample.
- Existing projects are SQLite-backed and account-owned. New city records will use a separate table and API to avoid changing existing project semantics.
- Baseline frontend production build was available; the repository includes pytest and Playwright regression suites. Existing files contain unrelated local modifications, which will be preserved.

## Implementation sequence

1. Add a separate `#city-builder` workspace and account-owned city-project API; keep the existing studio route and editor intact.
2. Expose a server-side asset adapter over verified gingerbread-house/storefront templates, with exact dimensions, revisions, 3D surfaces, thumbnails, paper formats, and printable status.
3. Implement integer-cell placement, conservative rotated footprints, collisions/bounds, drag/drop and click placement, move/rotate/duplicate/delete, bounded undo/redo, camera controls, inspector, and autosave.
4. Add validated JSON backup/import, reopen/new-village flows, print preflight, and a deterministic vector-preserving PDF export containing complete template page sets per physical instance plus a separately identified reference layout/calibration page.
5. Add focused geometry/persistence/PDF integration tests, run the regression suite and frontend build, and document known limits and physical QA status.

## Decisions and limits

- Default grid: 12 × 12 with 100 mm cells. Grid dimensions are configurable up to 32 × 32; cell size is configurable from 60 to 500 mm. Footprints use `ceil(template physical size / cellSize)` and swap axes at 90/270 degrees. Records store the occupied rectangle's top-left cell; the rendered model pivot is centered over that rectangle.
- Per-city limit: 100 objects. Export limits: 200 combined PDF pages and 100 MiB. No scaling, no printable road tiles in this phase; the editor grid is clearly non-printing.
- City records use the signed-in account's existing owner ID. JSON import preserves unknown asset references for warning/recovery, while invalid schema, bounds, grid, and placement collisions are rejected.
- The layout page is a reduced reference map explicitly labeled “not a printable base”; the 50 mm calibration ruler is placed on that generated guide page. Source template pages retain their original vectors and page boxes.
- Physical assembly is not validated by software. No physical print/cut/fold/glue trial has been performed for this feature.
