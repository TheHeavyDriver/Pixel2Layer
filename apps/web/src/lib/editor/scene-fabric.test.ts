import { describe, expect, it } from 'vitest';
import { Canvas, Group, Path, Rect, Point, Textbox, filters } from 'fabric';

import {
  canvasToScene,
  elementToFabric,
  sceneFiltersToFabric,
  sceneToCanvas,
  fabricToElement,
  resolveSrc,
} from '@/lib/editor/scene-fabric';
import type { SceneGraphElement } from '@pixel2layer/schema';
import { API_BASE } from '@/lib/api';
import { makeScene } from '@/test/fixtures';

function makeCanvas(): Canvas {
  return new Canvas(undefined, { width: 300, height: 200 });
}

describe('sceneToCanvas + canvasToScene round trip', () => {
  it('populates the canvas with one object per layer', async () => {
    const scene = makeScene();
    const canvas = makeCanvas();

    await sceneToCanvas(scene, canvas);

    expect(canvas.getObjects()).toHaveLength(3);
    const rect = canvas.getObjects()[0];
    expect(rect.get('p2lId')).toBe('rect-1');
  });

  it('preserves layer geometry and styling when read back', async () => {
    const scene = makeScene();
    const canvas = makeCanvas();

    await sceneToCanvas(scene, canvas);
    const readBack = canvasToScene(canvas, scene);

    const rect = readBack.layers.find((l) => l.id === 'rect-1') as Extract<SceneGraphElement, { type: 'rectangle' }>;
    const origRect = scene.layers[0] as Extract<SceneGraphElement, { type: 'rectangle' }>;
    expect(rect.width).toBeCloseTo(origRect.width, 0);
    expect(rect.height).toBeCloseTo(origRect.height, 0);
    expect(rect.fill).toBe('#FF5733');
    expect(rect.transform.x).toBeCloseTo(origRect.transform.x, 0);
    expect(rect.transform.y).toBeCloseTo(origRect.transform.y, 0);

    const text = readBack.layers.find((l) => l.id === 'txt-1') as Extract<SceneGraphElement, { type: 'text' }>;
    expect(text.content).toBe('Hello');
    expect(text.fontSize).toBe(24);
    expect(text.fontFamily).toBe('Arial');
  });

  it('removes objects whose ids vanished from the scene', async () => {
    const scene = makeScene();
    const canvas = makeCanvas();
    await sceneToCanvas(scene, canvas);

    scene.layers = scene.layers.slice(0, 2);
    await sceneToCanvas(scene, canvas);

    const canvasIds = canvas.getObjects().map((o) => o.get('p2lId'));
    expect(canvasIds).toEqual(['rect-1', 'txt-1']);
  });

  it('keeps z-order in sync with layer order', async () => {
    const scene = makeScene();
    const canvas = makeCanvas();
    await sceneToCanvas(scene, canvas);

    const topId = canvas.getObjects()[2]?.get('p2lId');
    expect(topId).toBe('cir-1');
  });
});

describe('fabricToElement', () => {
  it('reads scaled rectangle geometry at canvas-plane size', () => {
    const rect = new Rect({
      left: 10,
      top: 20,
      originX: 'center',
      originY: 'center',
      width: 100,
      height: 50,
      scaleX: 2,
      scaleY: 1,
      angle: 0,
      fill: '#123456',
    });
    const prev = makeScene().layers[0] as Extract<SceneGraphElement, { type: 'rectangle' }>;
    const el = fabricToElement(rect as never, prev, { scaleX: 2, scaleY: 1, angle: 0 }) as Extract<
      SceneGraphElement,
      { type: 'rectangle' }
    >;

    expect(el.width).toBe(200);
    expect(el.height).toBe(50);
    expect(el.transform.scaleX).toBe(1);
    expect(el.transform.y).toBe(20);
  });

  it('serializes a grouped rectangle at canvas-plane coordinates', () => {
    const inner = new Rect({
      width: 50,
      height: 30,
      originX: 'center',
      originY: 'center',
      fill: '#ababab',
    });
    inner.set('p2lId', 'g-rect');
    const group = new Group([inner]); // center-anchored by default
    group.set({ left: 40, top: 60, originX: 'center', originY: 'center' });

    const prev = makeScene().layers[0] as Extract<SceneGraphElement, { type: 'rectangle' }>;
    const prevInGroup = { ...prev, id: 'g-rect' };
    const layer = group.getObjects()[0] as never;
    const el = fabricToElement(layer, prevInGroup, { scaleX: 1, scaleY: 1, angle: 0 }) as Extract<
      SceneGraphElement,
      { type: 'rectangle' }
    >;

    // Child of a group: getCenterPoint should reflect group position + child offset.
    expect(el.transform.x).toBeCloseTo(40, 0);
    expect(el.width).toBe(50);
  });

  it('fast-paths textbox content and font props', () => {
    const box = new Textbox('Hi', {
      left: 5,
      top: 6,
      originX: 'center',
      originY: 'center',
      fontSize: 16,
      fontWeight: 400,
      fontFamily: 'Georgia',
      charSpacing: 25,
      lineHeight: 1.4,
    });
    const prev = makeScene().layers[1] as Extract<SceneGraphElement, { type: 'text' }>;
    const el = fabricToElement(box as never, prev, { scaleX: 1, scaleY: 1, angle: 0 }) as Extract<
      SceneGraphElement,
      { type: 'text' }
    >;

    expect(el.content).toBe('Hi');
    expect(el.letterSpacing).toBe(0.25);
    expect(el.lineHeight).toBe(1.4);
    expect(el.fontFamily).toBe('Georgia');
  });
});

describe('elementToFabric', () => {
  it('maps every supported element type to a fabric instance', () => {
    const scene = makeScene();
    for (const layer of scene.layers) {
      const obj = elementToFabric(layer as SceneGraphElement);
      expect(obj).not.toBeNull();
      expect(obj!.get('p2lId')).toBe(layer.id);
    }
  });

  it('marks locked elements non-selectable and pinned', () => {
    const scene = makeScene();
    const locked = {
      ...scene.layers[0],
      locked: true,
    };
    const obj = elementToFabric(locked as SceneGraphElement)!;
    expect(obj.selectable).toBe(false);
    expect(obj.lockMovementX).toBe(true);
    expect(obj.lockRotation).toBe(true);
  });
});

describe('round-trip with grouping', () => {
  it('flattens a group back into individual scene elements', async () => {
    const scene = makeScene();
    const canvas = makeCanvas();
    await sceneToCanvas(scene, canvas);

    const active = canvas.getObjects().map((o) => o);
    canvas.remove(...active);
    canvas.add(new Group(active as never[], { canvas }));
    canvas.requestRenderAll();

    const readBack = canvasToScene(canvas, scene);
    expect(readBack.layers).toHaveLength(3);
    const ids = readBack.layers.map((l) => l.id);
    expect(ids).toContain('rect-1');
    expect(ids).toContain('txt-1');
    expect(ids).toContain('cir-1');
  });
});

describe('Point usage for polygons', () => {
  it('builds a polygon from point tuples', () => {
    const scene = makeScene();
    const polygon = {
      ...scene.layers[2],
      id: 'poly-1',
      type: 'polygon' as const,
      points: [
        [0, 0],
        [10, 0],
        [10, 10],
      ] as Array<[number, number]>,
    };
    const obj = elementToFabric(polygon as SceneGraphElement)!;
    expect(obj.type).toBe('polygon');
  });
});

describe('v0.4: vectors and images', () => {
  it('creates a fabric Path for a vector element', () => {
    const scene = makeScene();
    const vector = {
      ...scene.layers[0],
      id: 'vec-1',
      type: 'vector' as const,
      path: 'M 0 0 L 10 0 L 10 10 Z',
      width: 10,
      height: 10,
    };
    const obj = elementToFabric(vector as SceneGraphElement)!;
    expect(obj.type).toBe('path');
    expect(obj.get('p2lId')).toBe('vec-1');
    expect((obj as Path).path as unknown).toBeTruthy();
  });

  it('resolves backend-relative image srcs against the API origin', () => {
    expect(resolveSrc('/api/storage/masked/u1/0.png')).toBe(
      `${API_BASE}/api/storage/masked/u1/0.png`,
    );
    expect(resolveSrc('https://cdn.example.com/a.png')).toBe(
      'https://cdn.example.com/a.png',
    );
    expect(resolveSrc('data:image/png;base64,iVBOR')).toBe('data:image/png;base64,iVBOR');
  });
});

describe('sceneFiltersToFabric', () => {
  it('returns an empty list when no filters are set', () => {
    expect(sceneFiltersToFabric(undefined)).toEqual([]);
  });

  it('maps each scene filter onto a fabric filter instance', () => {
    const out = sceneFiltersToFabric({
      brightness: 0.2,
      contrast: 0.5,
      saturation: -0.25,
      grayscale: true,
      invert: true,
      blur: 0.1,
    });

    expect(out).toHaveLength(6);
    expect(out[0]).toBeInstanceOf(filters.Brightness);
    expect((out[0] as unknown as { brightness: number }).brightness).toBe(0.2);
    expect(out[2]).toBeInstanceOf(filters.Saturation);
    expect(out[3]).toBeInstanceOf(filters.Grayscale);
    expect(out[4]).toBeInstanceOf(filters.Invert);
    expect(out[5]).toBeInstanceOf(filters.Blur);
  });

  it('skips missing filters', () => {
    const out = sceneFiltersToFabric({ invert: true });
    expect(out).toHaveLength(1);
  });
});