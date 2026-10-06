# Pixel2Layer — PERT Chart

Nine-step critical path from image upload to distribution. Arrows show dependencies (`A → B` = B needs A).

```
1. Foundations      [schema · upload · job queue · docker]
        ↓
2. Reconstruction   [OCR/text · shapes · colors → scene graph]
        ↓
3. Exports          [PNG/JPG/SVG export · .p2l round-trip]
        ↓
4. Editor           [Fabric canvas · layers · properties · undo/redo]
        ↓
5. Auth & Projects  [JWT login · project CRUD · version history]
        ↓
6. Fidelity         [vectorizer · segmentation · confidence UI]
        ↓
    ┌───────────────┴────────────────┐
    ↓                               ↓
7. Tools          8. Distribution
   [image filters ·        [sharing links · templates ·
    bg removal ·            batch processing · PDF]
    region editing · smart
    grouping]               ↑
    └───────────┬───────────┘
                ↓
9. Advanced Backlog
   [vector v1.1 · SAM 2 fine-tune · font matching]
```

## Steps & dependencies

| # | Step | Depends on | Deliverable |
|---|------|-----------|-------------|
| 1 | Foundations (v0.1) | — | SceneGraph schema, upload service, job queue, dev env |
| 2 | Reconstruction (v0.2) | 1 | OCR/text, shapes, colors → editable scene graph |
| 3 | Exports (v0.2) | 2 | PNG/JPG/SVG export + `.p2l` save/load |
| 4 | Editor (v0.2) | 3 | Fabric canvas: layers, properties, undo/redo |
| 5 | Auth & Projects (v0.3) | 4 | JWT auth, project CRUD, version history |
| 6 | Fidelity (v0.4) | 5 | Vector paths, segmentation, confidence UI |
| 7 | Image Tools (v0.4/v0.6) | 6 | Filters, bg removal, region editing, smart grouping |
| 8 | Distribution (v0.5) | 5, 6 | Sharing, templates, batch, PDF |
| 9 | Advanced (backlog) | 6, 7 | Vector v1.1, SAM 2 fine-tune, font matching |

## Notes

- Critical path: **1 → 2 → 3 → 4 → 5 → 6 → [7 or 8] → 9**.
- 7 and 8 are parallel once 5 and 6 land.
- 9 is optional over-engineering; ship only if reconstruction quality demands it.