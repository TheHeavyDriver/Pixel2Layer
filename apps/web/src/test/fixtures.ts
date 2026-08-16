import type { SceneGraph } from '@pixel2layer/schema';

export function makeScene(overrides: Partial<SceneGraph> = {}): SceneGraph {
  return {
    schemaVersion: 1,
    canvas: { width: 300, height: 200, background: '#F0F0F0' },
    layers: [
      {
        id: 'rect-1',
        type: 'rectangle',
        name: 'Background',
        transform: { x: 100, y: 150, scaleX: 1, scaleY: 1, rotation: 0 },
        width: 200,
        height: 100,
        fill: '#FF5733',
        opacity: 1,
        visible: true,
        locked: false,
        confidence: 0.92,
      },
      {
        id: 'txt-1',
        type: 'text',
        name: 'Title',
        transform: { x: 100, y: 50, scaleX: 1, scaleY: 1, rotation: 0 },
        content: 'Hello',
        fontFamily: 'Arial',
        fontSize: 24,
        fontWeight: 700,
        width: 120,
        fill: '#000000',
        opacity: 1,
        visible: true,
        locked: false,
        confidence: 0.8,
      },
      {
        id: 'cir-1',
        type: 'circle',
        name: 'Dot',
        transform: { x: 260, y: 170, scaleX: 1, scaleY: 1, rotation: 0 },
        radius: 12,
        fill: '#33C3FF',
        opacity: 1,
        visible: true,
        locked: false,
        confidence: 0.99,
      },
    ],
    confidence: { shapes: 0.8, text: 0.85 },
    overallConfidence: 0.82,
    ...overrides,
  };
}