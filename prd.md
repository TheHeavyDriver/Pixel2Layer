# PRD: Pixel2Layer — Image-to-Editable Design Platform

## Problem Statement

Most images distributed on the web — `poster.png`, `banner.jpg`, `flyer.jpeg`, social-media posts — are flattened raster files. When a design is exported to an image, every element (text, logos, icons, shapes, illustrations, backgrounds, gradients) is merged into pixels. The original editable structure is lost.

When a designer receives only the final image and needs to make a change, they must find the original file, ask the original designer for source, recreate the design manually, or remove-and-replace elements in Photoshop. This is extremely time-consuming and often impossible.

Users want: given any supported flat image, recover an editable structure — real text, geometric shapes, vector paths, independent colors, and layer relationships — and be able to edit it directly, then export the result.

## Solution

Pixel2Layer turns flattened images back into structured, editable designs. The core concept:

**Raster Image → Visual Analysis → Element Extraction → Editable Scene Graph → Design Editor**

- A user uploads a PNG/JPG/JPEG/WebP image.
- The backend asynchronously analyzes it: OCR for text, contour detection for shapes, color extraction, SAM 2-based segmentation for photographic regions, and vectorization for illustrations/logos.
- Each detected element is reconstructed as an independent, editable object in a **scene graph** document.
- The browser editor (Fabric.js) presents the scene graph as a canvas where the user directly manipulates elements — select, move, resize, rotate, recolor, edit text, change fonts, manage layers — with no AI prompt required. AI/computer vision works only during the import stage.
- The user exports to PNG/JPG/SVG/PDF, saves a reusable project, or grabs a shareable link to edit.

The product is closer to Figma/Canva/Illustrator with an automated image-to-editable-design import system than to an AI image chatbot.

## User Stories

1. As a designer, I want to upload a PNG/JPG/JPEG/WebP image, so that the system can analyze it and reconstruct an editable design.
2. As a user, I want to see the reconstruction progress in real time, so that I understand what stage (upload, text detection, shape detection, segmentation, vectorization) the pipeline is in.
3. As a user, I want to be notified when reconstruction completes, so that I can proceed to the editor without polling.
4. As a user, I want detected text to become actual editable text objects, so that I can change the content, font, size, weight, color, alignment, letter spacing, and line height.
5. As a user, I want text that cannot be reliably font-matched to be converted to vector outlines as a fallback, so that its appearance is preserved even when true text reconstruction is impossible.
6. As a user, I want simple shapes (rectangles, circles, ellipses, lines, polygons, rounded rectangles) to be reconstructed as geometric objects, so that I can resize, recolor, rotate, resize strokes, and adjust corner radii without losing quality.
7. As a user, I want detected areas to have their dominant colors and gradients extracted as independent fill/stroke properties, so that I can change one element's color without affecting unrelated elements.
8. As a user, I want illustrations and logos to be converted into vector paths (SVG-like), so that they remain crisp when resized and editable as paths.
9. As a user, I want photographs to be segmented into meaningful regions (foreground objects, backgrounds, regions), so that photographic elements can be extracted as independent masked image layers where possible.
10. As a user, I want the system to clearly distinguish between true reconstruction and approximate segmentation, so that I know when an element is an exact restoration versus an approximation.
11. As a user, I want each reconstructed element to carry a confidence score, so that I know which elements are likely accurate and which need manual verification.
12. As a user, I want an overall reconstruction confidence summary, so that I can gauge how faithful the whole reconstruction is.
13. As a user, I want the reconstructed design to load into a canvas editor, so that I can start editing immediately.
14. As a user, I want to click a canvas element to select it, so that I can manipulate it.
15. As a user, I want to drag elements to move them, so that I can change the layout.
16. As a user, I want to resize and rotate selected elements, so that I can adjust their scale and orientation.
17. As a user, I want to duplicate and delete elements, so that I can structure my design the way I need.
18. As a user, I want to multi-select elements, so that I can apply operations to several at once.
19. As a user, I want to group and ungroup elements, so that I can treat collections of objects as a single unit or break them apart.
20. As a user, I want align and distribute tools, so that I can quickly arrange elements relative to each other.
21. As a user, I want a layers panel that lists every reconstructed element, so that I can see the design's structure.
22. As a user, I want to select a layer to focus its object on the canvas, so that I can edit it even when it is hidden behind others.
23. As a user, I want to hide/show, lock/unlock, reorder, rename, duplicate, and delete layers, so that I can manage the document structure exactly like a professional design tool.
24. As a user, I want a properties panel that updates per element type (text, shape, image, vector), so that I can edit the correct attributes without hunting for them.
25. As a user, I want to edit text properties (content, font, size, weight, style, alignment, letter spacing, line height, color, transform, opacity, rotation, position), so that typography behaves like a real design tool.
26. As a user, I want to edit shape properties (fill, stroke, stroke width, opacity, corner radius, position, size, rotation), so that shapes remain fully editable geometry.
27. As a user, I want to edit image properties (width, height, position, rotation, opacity, crop, mask, filters), so that I can adjust photographs and image layers.
28. As a user, I want to edit vector properties (fill, stroke, stroke width, opacity, transform) and edit path control points, so that vectorized elements remain editable paths.
29. As a user, I want to set colors via HEX, RGB, and HSL with opacity and gradient support, so that color editing matches standard design workflows.
30. As a user, I want to undo and redo my edits, so that I can safely experiment without fear of breaking the design.
31. As a user, I want to save the project in an editable format (`.p2l`) containing the scene graph, assets, typography, layer structure, and editor metadata, so that I can close the browser and resume editing later.
32. As a user, I want to reopen previously saved projects, so that I can continue editing them.
33. As a user, I want to export the final design to PNG, JPG, SVG, and PDF, so that I can distribute it in any required format.
34. As a user, I want to save any reconstructed design as a reusable template, so that I don't have to rebuild common layouts.
35. As a user, I want to browse a template gallery, so that I can start new projects from proven layouts.
36. As a user, I want to create an account with email/password or OAuth, so that my projects and templates are stored and available across sessions.
37. As a user, I want to create, rename, delete, list, and view the history of my projects, so that I can manage my library.
38. As a user, I want version history for each project, so that I can restore earlier versions of my design.
39. As a user, I want to generate a shareable link for an editable design, so that I can let others view or edit it.
40. As a user, I want batch processing of multiple images, so that I can reconstruct many designs without uploading one at a time.

## Implementation Decisions

### Scope
The full product is covered in this PRD. MVP phases should be planned so each phase ships independently (see Further Notes) but all features below are in scope.

### Architecture
- **Frontend:** Next.js + React + TypeScript + Tailwind CSS, served on Vercel.
- **Editor canvas:** Fabric.js. Its mature scene graph, built-in manipulation controls (select/move/resize/rotate/group/align), and serialization make it the strongest fit. A hybrid (Fabric for manipulation + SVG for vector paths) is acceptable where Fabric's path editing is weaker.
- **Backend:** Python + FastAPI, deployed to Render/Railway/AWS.
- **Storage/database:** Supabase Storage for uploaded images, assets, and exports; PostgreSQL for projects, version history, templates, and sharing metadata.
- **Auth:** email/password and OAuth via Supabase Auth.

### Processing model
- **Async job queue:** uploads enqueue a reconstruction job; a worker pipeline reports per-stage progress and completion status. The client polls or receives updates (SSE/WebSocket) so long-running reconstructions never block.
- Image processing uses OpenCV, Pillow, and NumPy.
- OCR via PaddleOCR (primary), Tesseract/EasyOCR as fallbacks.
- Segmentation via SAM / SAM 2.
- Vectorization via Potrace + OpenCV contours with custom SVG path generation.

### Modules
The following deep modules are built or modified; each has a simple, stable interface and is tested in isolation:

- **UploadService** — validates uploads (type, size), stores originals in Supabase Storage, returns object references.
- **JobQueue** — async reconstruction orchestrator; owns job lifecycle, stage state, progress, failure handling, and completion notifications.
- **TextDetector** — OCR + font matching + per-text attribute inference (content, family, weight, size, color, letter spacing, line height, alignment, rotation, position). Emits real editable text, with vector-outline fallback when font confidence is low.
- **ShapeDetector** — reconstructs rectangles, circles, ellipses, lines, polygons, and rounded rectangles from contours, preserving exact geometry parameters.
- **ColorExtractor** — extracts dominant colors and gradients per region into fill/stroke properties.
- **Segmenter** — SAM 2-based segmentation for photographic regions; produces masked image layers and region metadata. Marks output as approximate.
- **Vectorizer** — converts boundaries and edges of illustrations/logos into SVG-compatible paths.
- **SceneGraphBuilder** — composes all detected elements into the canonical scene graph document with correct layering order.
- **ConfidenceScorer** — produces per-element confidence and overall reconstruction confidence.
- **ExportService** — exports PNG/JPG/SVG/PDF and serializes/deserializes the `.p2l` editable project format.
- **ProjectService** — auth integration, project CRUD, version history, templates, sharing links, and batch job tracking.

### Shared contracts
- **SceneGraphSchema** — the canonical JSON document and API contract shared between backend and frontend. Defines element types (text, rectangle, circle, ellipse, line, polygon, path/vector, image), their properties, layer ordering, canvas metadata, and per-element confidence. The `.p2l` format is a superset (adds assets, typography, editor metadata).
- Backend ↔ frontend API is defined by these schemas; frontend rendering and backend reconstruction both depend on them so changes are coordinated.

### Key clarifications
- Editing is deterministic and user-controlled; AI/CV runs only at import time. No prompt-based editing.
- Confidence is always surfaced to the user, per element and overall.
- Text fallback: editable text preferred; vector outlines preserve appearance when font cannot be confidently identified.
- No live multiplayer. Sharing is read/edit links plus version history.

## Testing Decisions

### Testing philosophy
Good tests assert external behavior of a module through its public interface, not implementation details. Fixtures are real images (synthetic posters and screenshots) so tests reflect actual user inputs, and expected scene-graph outputs are golden files.

### Modules to test
- **ShapeDetector** — synthetic images of known circles/rectangles/polygons reconstruct with correct geometry and near-exact parameters; noisy images still produce plausible bounds.
- **ColorExtractor** — dominant color and gradient extraction matches ground-truth fixtures within tolerance.
- **SceneGraphBuilder** — given a set of detected element fixtures, produces a valid, ordered, schema-compliant scene graph; invalid/missing element cases fail gracefully.
- **JobQueue** — lifecycle transitions (queued → running → done/failed), progress updates, retry on worker failure, and completion notification behavior.
- **ProjectService** — project CRUD, version history semantics, share-link access control, and template round-tripping via the Testcontainers-style isolated Postgres (or SQLite in-memory for unit-level tests).
- **SceneGraphSchema** — schema validation (draft type checking) and `.p2l` round-trips: serialize → deserialize → serialize yields identical structure.
- **ExportService** — PNG/JPG/SVG/PDF exports produce valid, non-empty files that render to the expected dimensions; `.p2l` round-trips.

### Prior art
Test style follows standard pytest patterns (asserts over public interfaces, fixture-based inputs, golden-file comparisons). Where migration or data concerns arise, use the Supabase Postgres best-practices guidance. Editor behavior (Fabric.js interactions) is exercised through e2e tests rather than unit tests, matching its canvas-centric nature.

## Out of Scope

- Live real-time multiplayer collaboration (CRDTs).
- Native mobile/desktop applications (web only in this PRD).
- Complex image-generation/AI-prompt editing — the system does not generate new designs from prompts.
- Guaranteed perfect reconstruction of arbitrary photographs into true original layers — this information does not exist in a flattened image; segmentation is always approximate and labeled as such.
- Font licensing/ordering system, marketplace, or payments.
- Full design-system features such as auto-layout, components/variants, or plugin SDK.
- Print/CMYK color management and prepress export.

## Further Notes

### Phasing suggestion
Although the full product is documented here, implement in phases so each ships value:

- **Phase 1 — Core MVP:** upload, async pipeline for text + flat-color shapes, scene graph, Fabric editor with layers/properties panels, export PNG/JPG/SVG, `.p2l` save/load.
- **Phase 2 — Auth & persistence:** accounts, project library, version history.
- **Phase 3 — Vectorization & segmentation:** Potrace vectorization, SAM 2 segmentation, confidence display, harder-image handling.
- **Phase 4 — Sharing, templates, batch:** share links, template gallery, batch uploads, PDF export.

### Progressive reconstruction
Simple graphic designs (text, shapes, flat colors, logos) reconstruct with high fidelity. Complex photographs remain raster-based or approximately segmented. The confidence system makes this transparency a product feature, not a limitation.

### Project identity and future
Beyond recovering editable designs, the platform can grow toward templates, sharing, and collaboration once the core reconstruction + editing loop is reliable. The scene graph and `.p2l` format are the durable foundation everything else builds on.