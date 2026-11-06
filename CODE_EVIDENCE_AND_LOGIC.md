# Code Evidence and Logic

## <span style="font-size: 18pt">EVIDENCE: Canvas Viewport Scaling Logic</span>

### <span style="font-size: 18pt">Code Excerpt</span>

```typescript
// From: apps/web/src/components/editor/canvas-editor.tsx (lines 118-140)

const fitToViewport = useCallback((canvas: Canvas) => {
  if (fabricRef.current !== canvas) return;
  
  // Get the editing area (viewport) dimensions
  const { width: viewW, height: viewH } = getViewSize(canvas);
  
  // Get the original scene (uploaded image) dimensions
  const sceneW = sceneRef.current.canvas.width || 900;
  const sceneH = sceneRef.current.canvas.height || 600;
  
  // Resize the HTML canvas element to fill the viewport
  canvas.setDimensions({ width: viewW, height: viewH });
  
  // Compute contain-fit: scale the scene to fit inside viewport
  const { zoom, tx, ty } = computeContainViewport(viewW, viewH, sceneW, sceneH);
  
  // Apply the scaling transform
  const safeZoom = Number.isFinite(zoom) && zoom > 0 
    ? Math.min(100, Math.max(0.001, zoom)) 
    : 1;
  canvas.setViewportTransform([safeZoom, 0, 0, safeZoom, tx, ty]);
  canvas.requestRenderAll();
  manualZoomRef.current = false;
}, [getViewSize]);
```

### <span style="font-size: 18pt">Logic Explanation</span>

**Purpose of the logic:**
- Fits the uploaded image (scene) into the available editing area (viewport) while maintaining aspect ratio
- The HTML canvas element fills the viewport, and the scene is scaled via transform

**Input and output:**
- Input: Canvas instance, container dimensions, scene dimensions
- Output: Canvas element resized to viewport, viewport transform applies zoom/translation

**Key condition or algorithm:**
- Uses `computeContainViewport` to calculate uniform zoom that fits the scene inside viewport
- Scene dimensions remain 1:1 in scene space (not stretched/cropped)
- Viewport transform applies the scale, not the object/layer scales

**Error handling:**
- Guards against disposed canvas via `fabricRef.current !== canvas` check
- Clamps zoom to reasonable bounds (0.001 to 100)
- Falls back to 1.0 if zoom is not finite

**Complexity or performance:**
- O(1) computation
- Triggers on: initial load, window resize, scene change, container resize
- ResizeObserver efficiently tracks container size changes

---

## Repository / branch / commit

**Repository:** Pixel2Layer  
**Branch:** main  
**Last commit:** Row 95 in memory.md (8 commits for BGR fix, text-gating, schema alignment, canvas fixes)

---

# Programming Concepts Applied

## [Concept 1] Viewport Transform Pattern

- **Where used:** Canvas editor rendering system
- **Evidence:** 
  - Function: `fitToViewport` (canvas-editor.tsx:118-140)
  - Helper: `computeContainViewport` (viewport.ts)
  - Pattern: Separates scene coordinates from display coordinates via transform matrix

## [Concept 2] Async Image Loading with Fabric.js

- **Where used:** Scene-to-canvas synchronization
- **Evidence:**
  - Function: `loadImageElement` (scene-fabric.ts:444-470)
  - Function: `sceneToCanvas` (scene-fabric.ts:39-88)
  - Algorithm: Loads images async, scales them to match scene element dimensions

## [Concept 3] React useRef for Mutable Instance State

- **Where used:** Canvas lifecycle management
- **Evidence:**
  - Variables: `fabricRef`, `lastSyncedRef`, `manualZoomRef`, `sceneRef` (canvas-editor.tsx:61-68)
  - Reason: Fabric canvas instance persists across renders; refs avoid recreating

## [Concept 4] Coordinate System Transformation

- **Where used:** Scene element positioning and scaling
- **Evidence:**
  - Module: scene-fabric.ts (full file)
  - Functions: `elementToFabric`, `fabricToElement`, `fabricBase`
  - Pattern: Center-origin convention for all elements, composed transforms for nested groups

## [Concept 5] Observer Pattern (ResizeObserver)

- **Where used:** Responsive canvas resizing
- **Evidence:**
  - Effect hook: canvas-editor.tsx:233-259
  - Observer: ResizeObserver watches container element
  - Action: Refits or resizes canvas when editing area dimensions change

## [Concept 6] Liveness Checking for Async Operations

- **Where used:** Preventing stale async updates after component unmount
- **Evidence:**
  - Parameter: `isCurrent` callback in `sceneToCanvas` (scene-fabric.ts:42)
  - Check: `if (fabricRef.current !== canvas) return;` (scene-fabric.ts:66, 79, 156)
  - Pattern: Validates canvas identity before mutating after await points

## [Concept 7] Immutable Data Updates with Spread Operator

- **Where used:** Scene graph state management
- **Evidence:**
  - Function: `canvasToScene` (scene-fabric.ts:363-380)
  - Function: `fabricToElement` (scene-fabric.ts:258-358)
  - Pattern: Returns new scene graph object with updated layers array

## [Concept 8] Type Guards and Discriminated Unions

- **Where used:** Element type handling
- **Evidence:**
  - Function: `elementToFabric` (scene-fabric.ts:90-221)
  - Function: `fabricToElement` (scene-fabric.ts:225-359)
  - Pattern: Switch on `element.type` to narrow SceneGraphElement union type
