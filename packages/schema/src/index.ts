/**
 * SceneGraphSchema — the canonical scene graph document.
 *
 * This is the single source of truth for the JSON contract shared between
 * the backend (reconstruction pipeline) and the frontend (Fabric editor).
 * Versioning: bump `SCENE_GRAPH_SCHEMA_VERSION` on any breaking change and
 * coordinate releases on both sides.
 */
export const SCENE_GRAPH_SCHEMA_VERSION = 1;

export type ElementType =
  | 'text'
  | 'rectangle'
  | 'circle'
  | 'ellipse'
  | 'line'
  | 'polygon'
  | 'vector'
  | 'image';

/** 0..1 confidence that a reconstructed element is faithful. */
export type Confidence = number;

/** Shared transform + style fields carried by every element. */
export interface Transform {
  x: number;
  y: number;
  scaleX: number;
  scaleY: number;
  rotation: number; // degrees, clockwise
}

export interface OutlineStyle {
  stroke?: string;
  strokeWidth?: number;
  strokeDashArray?: number[];
  opacity: number;
}

export interface ElementBase {
  id: string;
  type: ElementType;
  name: string;
  transform: Transform;
  fill?: string;
  stroke?: string;
  strokeWidth?: number;
  strokeDashArray?: number[];
  opacity: number;
  visible: boolean;
  locked: boolean;
  confidence: Confidence;
  /** optional prose explaining what the confidence means */
  confidenceNote?: string;
}

export interface TextElement extends ElementBase {
  type: 'text';
  content: string;
  fontFamily: string;
  fontSize: number;
  fontWeight: number;
  fontStyle?: 'normal' | 'italic';
  textAlign?: 'left' | 'center' | 'right' | 'justify';
  letterSpacing?: number;
  lineHeight?: number;
  width: number; // layout box width (px)
}

export interface RectElement extends ElementBase {
  type: 'rectangle';
  width: number;
  height: number;
  rx?: number;
  ry?: number;
}

export interface CircleElement extends ElementBase {
  type: 'circle';
  radius: number;
}

export interface EllipseElement extends ElementBase {
  type: 'ellipse';
  rx: number;
  ry: number;
}

export interface LineElement extends ElementBase {
  type: 'line';
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface PolygonElement extends ElementBase {
  type: 'polygon';
  points: Array<[number, number]>;
}

export interface VectorElement extends ElementBase {
  type: 'vector';
  /** SVG path data in the element's local coordinate space */
  path: string;
  width: number;
  height: number;
}

export interface ImageElement extends ElementBase {
  type: 'image';
  /** storage reference for the source asset */
  src: string;
  width: number;
  height: number;
  crop?: { x: number; y: number; width: number; height: number };
  /** per-element image adjustments (v0.6 editor backlog) */
  filters?: {
    brightness?: number;
    contrast?: number;
    saturation?: number;
    grayscale?: boolean;
    invert?: boolean;
    blur?: number;
  };
}

export type SceneGraphElement =
  | TextElement
  | RectElement
  | CircleElement
  | EllipseElement
  | LineElement
  | PolygonElement
  | VectorElement
  | ImageElement;

export interface SceneGraph {
  schemaVersion: number;
  canvas: {
    width: number;
    height: number;
    background: string | null; // null = transparent
  };
  /** ordered back-to-front */
  layers: SceneGraphElement[];
  /** confidence breakdown per detected category */
  confidence: Record<string, Confidence>;
  /** aggregate reconstruction quality 0..1 */
  overallConfidence: Confidence;
  /** progressive-routing metadata (v0.4) */
  complexity?: { kind?: 'graphic' | 'photographic'; score?: number } | null;
}