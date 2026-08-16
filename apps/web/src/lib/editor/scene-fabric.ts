import type { SceneGraph, SceneGraphElement, Transform } from '@pixel2layer/schema';
import {
  ActiveSelection,
  Canvas,
  Circle,
  Ellipse,
  FabricImage,
  Group,
  Line,
  Path,
  Point,
  Polygon,
  Rect,
  Textbox,
  filters,
  type Object as FabricObject,
} from 'fabric';

import { API_BASE } from '@/lib/api';

/** Fabric objects carry the originating scene element id so we can round-trip. */
const ID_PROP = 'p2lId';
const TYPE_PROP = 'p2lType';
const LOCK_PROP = 'p2lLocked';

export interface FabricWithMeta extends FabricObject {
  [ID_PROP]?: string;
  [TYPE_PROP]?: string;
  [LOCK_PROP]?: boolean;
}

export async function sceneToCanvas(scene: SceneGraph, canvas: Canvas): Promise<void> {
  canvas.setDimensions({ width: scene.canvas.width, height: scene.canvas.height });
  canvas.backgroundColor = scene.canvas.background ?? 'transparent';

  const existing = new Map<string, FabricWithMeta>();
  (canvas.getObjects() as FabricWithMeta[]).forEach((obj) => {
    const id = obj[ID_PROP];
    if (id) existing.set(id, obj);
  });

  // Remove objects that are no longer in the scene (or in a different order later).
  const desiredIds = new Set(scene.layers.map((l) => l.id));
  for (const [id, obj] of existing) {
    if (!desiredIds.has(id)) canvas.remove(obj);
  }

  for (const element of scene.layers) {
    const existingObj = existing.get(element.id);
    if (existingObj) {
      applyElementToFabric(existingObj, element);
    } else if (element.type === 'image') {
      const loaded = await loadImageElement(element);
      if (loaded) canvas.add(loaded);
    } else {
      const built = elementToFabric(element);
      if (built) canvas.add(built);
    }
  }

  // Keep z-order in sync with scene.layers (back-to-front) regardless of edits.
  scene.layers.forEach((element, index) => {
    const obj = (canvas.getObjects() as FabricWithMeta[]).find((o) => o[ID_PROP] === element.id);
    if (obj) canvas.moveObjectTo(obj, index);
  });

  canvas.requestRenderAll();
}

export function elementToFabric(element: SceneGraphElement): FabricWithMeta | null {
  const base = fabricBase(element.transform);
  const common = {
    [ID_PROP]: element.id,
    [TYPE_PROP]: element.type,
    fill: element.fill ?? 'transparent',
    stroke: element.stroke ?? undefined,
    strokeWidth: element.strokeWidth ?? undefined,
    strokeDashArray: element.strokeDashArray ?? undefined,
    opacity: element.opacity,
    visible: element.visible,
    // locked objects are non-selectable and immobile
    selectable: !element.locked,
    evented: !element.locked,
    lockMovementX: element.locked,
    lockMovementY: element.locked,
    lockScalingX: element.locked,
    lockScalingY: element.locked,
    lockRotation: element.locked,
    [LOCK_PROP]: element.locked,
  };

  switch (element.type) {
    case 'rectangle':
      return new Rect({
        ...base,
        ...common,
        width: element.width,
        height: element.height,
        rx: element.rx ?? 0,
        ry: element.ry ?? 0,
        scaleX: element.transform.scaleX,
        scaleY: element.transform.scaleY,
        angle: element.transform.rotation,
      });
    case 'circle':
      return new Circle({
        ...base,
        ...common,
        radius: element.radius,
        scaleX: element.transform.scaleX,
        scaleY: element.transform.scaleY,
        angle: element.transform.rotation,
      });
    case 'ellipse':
      return new Ellipse({
        ...base,
        ...common,
        rx: element.rx,
        ry: element.ry,
        scaleX: element.transform.scaleX,
        scaleY: element.transform.scaleY,
        angle: element.transform.rotation,
      });
    case 'line':
      return new Line([element.x1, element.y1, element.x2, element.y2], {
        stroke: element.stroke ?? '#000000',
        strokeWidth: element.strokeWidth ?? 1,
        strokeDashArray: element.strokeDashArray ?? undefined,
        opacity: element.opacity,
        visible: element.visible,
        selectable: !element.locked,
        evented: !element.locked,
        lockMovementX: element.locked,
        lockMovementY: element.locked,
        lockScalingX: element.locked,
        lockScalingY: element.locked,
        lockRotation: element.locked,
        [ID_PROP]: element.id,
        [TYPE_PROP]: element.type,
        [LOCK_PROP]: element.locked,
      } as Record<string, unknown>);
    case 'polygon':
      return new Polygon(
        element.points.map(([x, y]) => new Point(x, y)),
        {
          ...base,
          ...common,
          scaleX: element.transform.scaleX,
          scaleY: element.transform.scaleY,
          angle: element.transform.rotation,
        },
      );
    case 'vector': {
      const path = new Path(element.path, {
        ...base,
        ...common,
        scaleX: element.transform.scaleX,
        scaleY: element.transform.scaleY,
        angle: element.transform.rotation,
      });
      return path;
    }
    case 'text':
      return new Textbox(element.content, {
        left: element.transform.x,
        top: element.transform.y,
        originX: 'center',
        originY: 'center',
        width: element.width,
        minWidth: 20,
        fontSize: element.fontSize,
        fontFamily: element.fontFamily,
        fontWeight: element.fontWeight,
        fontStyle: element.fontStyle ?? 'normal',
        textAlign: element.textAlign ?? 'left',
        charSpacing: (element.letterSpacing ?? 0) * 100,
        lineHeight: element.lineHeight ?? 1.2,
        scaleX: element.transform.scaleX,
        scaleY: element.transform.scaleY,
        angle: element.transform.rotation,
        fill: element.fill ?? '#000000',
        opacity: element.opacity,
        visible: element.visible,
        selectable: !element.locked,
        evented: !element.locked,
        lockMovementX: element.locked,
        lockMovementY: element.locked,
        lockScalingX: element.locked,
        lockScalingY: element.locked,
        lockRotation: element.locked,
        [ID_PROP]: element.id,
        [TYPE_PROP]: element.type,
        [LOCK_PROP]: element.locked,
      } as Record<string, unknown>);
    case 'image':
      // image elements need async loading; handled separately.
      return null;
    default:
      return null;
  }
}

/** Apply the current canvas state of an object back onto its scene element.
 *  `eff` carries the composed scale/rotation inherited from any parent group. */
export function fabricToElement(
  obj: FabricWithMeta,
  prev: SceneGraphElement,
  eff: EffTransform,
): SceneGraphElement {
  // canvas-plane center (accounts for nested group transforms)
  let cx = obj.left ?? 0;
  let cy = obj.top ?? 0;
  try {
    const c = obj.getCenterPoint();
    cx = c.x;
    cy = c.y;
  } catch {
    // fall back to left/top
  }
  const transform: Transform = {
    x: cx,
    y: cy,
    scaleX: 1,
    scaleY: 1,
    rotation: eff.angle ?? obj.angle ?? 0,
  };
  const base = {
    id: prev.id,
    name: prev.name,
    transform,
    opacity: obj.opacity,
    visible: obj.visible,
    locked: obj[LOCK_PROP] ?? false,
    confidence: prev.confidence,
    confidenceNote: prev.confidenceNote,
  };

  switch (prev.type) {
    case 'rectangle': {
      const o = obj as Rect;
      return {
        ...base,
        type: 'rectangle',
        width: Math.max(1, o.width * (eff.scaleX || 1)),
        height: Math.max(1, o.height * (eff.scaleY || 1)),
        rx: (o.rx ?? 0) || undefined,
        ry: (o.ry ?? 0) || undefined,
        fill: obj.fill as string | undefined,
        stroke: obj.stroke as string | undefined,
        strokeWidth: obj.strokeWidth,
        strokeDashArray: obj.strokeDashArray,
      } as SceneGraphElement;
    }
    case 'circle': {
      const o = obj as Circle;
      return {
        ...base,
        type: 'circle',
        radius: Math.max(1, o.radius * (eff.scaleX || 1)),
        fill: obj.fill as string | undefined,
        stroke: obj.stroke as string | undefined,
        strokeWidth: obj.strokeWidth,
        strokeDashArray: obj.strokeDashArray,
      } as SceneGraphElement;
    }
    case 'ellipse': {
      const o = obj as Ellipse;
      return {
        ...base,
        type: 'ellipse',
        rx: Math.max(1, o.rx * (eff.scaleX || 1)),
        ry: Math.max(1, o.ry * (eff.scaleY || 1)),
        fill: obj.fill as string | undefined,
        stroke: obj.stroke as string | undefined,
        strokeWidth: obj.strokeWidth,
        strokeDashArray: obj.strokeDashArray,
      } as SceneGraphElement;
    }
    case 'line': {
      const o = obj as Line;
      return {
        ...base,
        type: 'line',
        x1: o.x1,
        y1: o.y1,
        x2: o.x2,
        y2: o.y2,
        stroke: obj.stroke as string | undefined,
        strokeWidth: obj.strokeWidth,
        strokeDashArray: obj.strokeDashArray,
        transform: { x: 0, y: 0, scaleX: 1, scaleY: 1, rotation: 0 },
      } as SceneGraphElement;
    }
    case 'polygon': {
      const o = obj as Polygon;
      return {
        ...base,
        type: 'polygon',
        points: (o.points ?? []).map((p) => [p.x, p.y] as [number, number]),
        fill: obj.fill as string | undefined,
        stroke: obj.stroke as string | undefined,
        strokeWidth: obj.strokeWidth,
        strokeDashArray: obj.strokeDashArray,
        transform: { x: 0, y: 0, scaleX: 1, scaleY: 1, rotation: 0 },
      } as SceneGraphElement;
    }
    case 'vector': {
      const o = obj as Path;
      return {
        ...base,
        type: 'vector',
        path: segmentsToPathString(o.path),
        width: o.width * (eff.scaleX || 1),
        height: o.height * (eff.scaleY || 1),
        transform,
      } as SceneGraphElement;
    }
    case 'text': {
      const o = obj as Textbox;
      return {
        ...base,
        type: 'text',
        content: o.text ?? '',
        fontFamily: o.fontFamily,
        fontSize: o.fontSize * (eff.scaleY || 1),
        fontWeight: o.fontWeight,
        fontStyle: o.fontStyle,
        textAlign: o.textAlign,
        letterSpacing: (o.charSpacing ?? 0) / 100,
        lineHeight: o.lineHeight,
        width: o.width * (eff.scaleX || 1),
        fill: obj.fill as string | undefined,
        transform: { ...transform, scaleX: 1, scaleY: 1 },
      } as SceneGraphElement;
    }
    default:
      return prev;
  }
}

/** Read the live canvas back into a canonical scene graph.
 *  Groups are flattened: children are serialized at canvas-plane geometry. */
export function canvasToScene(canvas: Canvas, prev: SceneGraph): SceneGraph {
  const leaves = flattenToLeaves(canvas.getObjects() as FabricObject[], { scaleX: 1, scaleY: 1, angle: 0 });
  const byId = new Map<string, { obj: FabricWithMeta; eff: EffTransform }>();
  for (const leaf of leaves) {
    const id = leaf.obj[ID_PROP];
    if (id) byId.set(id, leaf);
  }
  const layers: SceneGraphElement[] = prev.layers
    .filter((el) => byId.has(el.id))
    .map((el) => {
      const { obj, eff } = byId.get(el.id)!;
      return fabricToElement(obj, el, eff);
    });
  return {
    ...prev,
    layers,
  };
}

interface EffTransform {
  scaleX: number;
  scaleY: number;
  angle: number;
}

/** Recursively collect objects, composing group-relative transforms onto children. */
function flattenToLeaves(objects: FabricObject[], inherited: EffTransform): { obj: FabricWithMeta; eff: EffTransform }[] {
  const out: { obj: FabricWithMeta; eff: EffTransform }[] = [];
  for (const o of objects) {
    const scaleX = (inherited.scaleX || 1) * (o.scaleX || 1);
    const scaleY = (inherited.scaleY || 1) * (o.scaleY || 1);
    const angle = (inherited.angle || 0) + (o.angle || 0);
    const isGrouped = Boolean(o.type === 'group' && o instanceof Group);
    if (isGrouped) {
      out.push(...flattenToLeaves((o as unknown as Group).getObjects() as unknown as FabricObject[], { scaleX, scaleY, angle }));
    } else {
      out.push({ obj: o as FabricWithMeta, eff: { scaleX, scaleY, angle } });
    }
  }
  return out;
}

export function applyElementToFabric(obj: FabricWithMeta, element: SceneGraphElement): void {
  const center = fabricBase(element.transform);
  if (element.type === 'image' && obj.type !== 'image') return; // only live image objects update in place
  obj.set({
    ...center,
    angle: element.transform.rotation,
    opacity: element.opacity,
    visible: element.visible,
    fill: element.fill ?? 'transparent',
    stroke: element.stroke ?? obj.stroke,
    strokeWidth: element.strokeWidth ?? obj.strokeWidth,
    strokeDashArray: element.strokeDashArray ?? obj.strokeDashArray,
    selectable: !element.locked,
    evented: !element.locked,
    lockMovementX: element.locked,
    lockMovementY: element.locked,
    lockScalingX: element.locked,
    lockScalingY: element.locked,
    lockRotation: element.locked,
    [LOCK_PROP]: element.locked,
  });
  if (element.type === 'image') {
    const fab = obj as FabricWithMeta & { filters?: unknown[] };
    fab.filters = sceneFiltersToFabric(element.filters);
    (obj as unknown as { applyFilters(): void }).applyFilters?.();
  }
}

function fabricBase(t: Transform) {
  return {
    left: t.x,
    top: t.y,
    originX: 'center' as const,
    originY: 'center' as const,
    scaleX: t.scaleX,
    scaleY: t.scaleY,
  };
}

export async function loadImageElement(
  element: SceneGraphElement & { type: 'image' },
): Promise<FabricWithMeta | null> {
  try {
    const img = await FabricImage.fromURL(resolveSrc(element.src), { crossOrigin: 'anonymous' });
    img.filters = sceneFiltersToFabric(element.filters);
    img.applyFilters();
    img.set({
      left: element.transform.x,
      top: element.transform.y,
      originX: 'center',
      originY: 'center',
      scaleX: (element.transform.scaleX || 1) * (element.width / (img.width || 1)),
      scaleY: (element.transform.scaleY || 1) * (element.height / (img.height || 1)),
      angle: element.transform.rotation,
      opacity: element.opacity,
      visible: element.visible,
      selectable: !element.locked,
      [ID_PROP]: element.id,
      [TYPE_PROP]: element.type,
      [LOCK_PROP]: element.locked,
    } as Record<string, unknown>);
    return img as unknown as FabricWithMeta;
  } catch {
    return null;
  }
}

export { ActiveSelection, FabricImage };

/** Resolve a scene-element asset ref to a loadable URL.
 *  Backend-emitted refs are API-relative (`/api/storage/...`); absolute URLs
 *  and data URIs pass through unchanged. */
export function resolveSrc(src: string): string {
  if (src.startsWith('/')) return `${API_BASE}${src}`;
  return src;
}

/** Serialize fabric path segments into an SVG path string for the scene graph. */
function segmentsToPathString(segments: unknown): string {
  if (typeof segments === 'string') return segments;
  if (!Array.isArray(segments)) return '';
  return segments
    .map((seg) => {
      if (!Array.isArray(seg)) return '';
      return seg
        .map((part) => (typeof part === 'number' ? round(part) : String(part)))
        .join(' ');
    })
    .join(' ');
}

function round(n: number): string {
  return String(Math.round(n * 1000) / 1000);
}

/** Map scene-graph image filters onto Fabric filter instances. */
export function sceneFiltersToFabric(
  f?: Extract<SceneGraphElement, { type: 'image' }>['filters'],
): InstanceType<typeof filters.BaseFilter<string>>[] {
  const out: InstanceType<typeof filters.BaseFilter<string>>[] = [];
  if (!f) return out;
  if (f.brightness) out.push(new filters.Brightness({ brightness: f.brightness })) as never;
  if (f.contrast) out.push(new filters.Contrast({ contrast: f.contrast })) as never;
  if (f.saturation) out.push(new filters.Saturation({ saturation: f.saturation })) as never;
  if (f.grayscale) out.push(new filters.Grayscale({ mode: 'luminosity' })) as never;
  if (f.invert) out.push(new filters.Invert()) as never;
  if (f.blur) out.push(new filters.Blur({ blur: f.blur })) as never;
  return out;
}