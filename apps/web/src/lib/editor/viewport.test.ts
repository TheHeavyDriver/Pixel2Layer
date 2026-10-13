import { describe, expect, it } from 'vitest';

import { computeContainViewport, computeWheelZoom } from '@/lib/editor/viewport';

describe('computeContainViewport', () => {
  it('fits the whole scene inside the view with no cropping', () => {
    // landscape scene in a portrait-ish view (and vice versa below)
    const v = computeContainViewport(800, 600, 1200, 900);
    expect(v.zoom).toBeCloseTo(800 / 1200, 6);
    // scaled scene must be fully inside the view on both axes
    expect(1200 * v.zoom).toBeLessThanOrEqual(800 + 1e-9);
    expect(900 * v.zoom).toBeLessThanOrEqual(600 + 1e-9);
  });

  it('preserves aspect ratio exactly (uniform scale, centered)', () => {
    const cases: Array<[number, number, number, number]> = [
      [1200, 700, 1080, 1920], // tall portrait upload in wide editor
      [1200, 700, 1920, 1080], // wide panorama in editor
      [800, 600, 100, 100], // tiny upload scales up, still square
      [800, 600, 4000, 3000], // huge upload scales down
      [600, 600, 300, 200], // fixture scene
    ];
    for (const [viewW, viewH, sceneW, sceneH] of cases) {
      const { zoom, tx, ty } = computeContainViewport(viewW, viewH, sceneW, sceneH);
      // uniform zoom by construction
      expect(zoom).toBeGreaterThan(0);
      expect(Number.isFinite(zoom)).toBe(true);
      // no cropping: scaled scene fits on both axes
      expect(sceneW * zoom).toBeLessThanOrEqual(viewW + 1e-9);
      expect(sceneH * zoom).toBeLessThanOrEqual(viewH + 1e-9);
      // at least one axis fits exactly (contain, not arbitrary shrink)
      const fillsX = Math.abs(sceneW * zoom - viewW) < 1e-9;
      const fillsY = Math.abs(sceneH * zoom - viewH) < 1e-9;
      expect(fillsX || fillsY).toBe(true);
      // centered: leftover space split evenly
      expect(tx).toBeCloseTo((viewW - sceneW * zoom) / 2, 6);
      expect(ty).toBeCloseTo((viewH - sceneH * zoom) / 2, 6);
      // aspect ratio unchanged
      expect(sceneW * zoom / (sceneH * zoom)).toBeCloseTo(sceneW / sceneH, 9);
    }
  });

  it('falls back to identity on degenerate sizes (no NaN/Infinity zoom)', () => {
    for (const args of [
      [0, 600, 300, 200],
      [800, 0, 300, 200],
      [800, 600, 0, 200],
      [800, 600, 300, 0],
    ] as Array<[number, number, number, number]>) {
      const v = computeContainViewport(...args);
      expect(v).toEqual({ zoom: 1, tx: 0, ty: 0 });
    }
  });
});

describe('computeWheelZoom', () => {
  it('zooms in on wheel-up (negative deltaY) and out on wheel-down', () => {
    expect(computeWheelZoom(1, -100)).toBeGreaterThan(1);
    expect(computeWheelZoom(1, 100)).toBeLessThan(1);
  });

  it('is smooth: a single tick changes zoom only slightly', () => {
    const up = computeWheelZoom(1, -100);
    const down = computeWheelZoom(1, 100);
    expect(up).toBeLessThan(1.2);
    expect(down).toBeGreaterThan(0.8);
  });

  it('compounds: repeated ticks keep moving in the same direction', () => {
    const z1 = computeWheelZoom(1, -100);
    const z2 = computeWheelZoom(z1, -100);
    expect(z2).toBeGreaterThan(z1);
  });

  it('clamps to sane bounds (never 0, negative, or huge)', () => {
    expect(computeWheelZoom(1, 1_000_000)).toBe(0.01);
    expect(computeWheelZoom(1, -1_000_000)).toBe(100);
    expect(computeWheelZoom(NaN, -100)).toBeGreaterThan(0);
  });

  it('stays uniform (single scalar) so aspect ratio cannot distort', () => {
    const z = computeWheelZoom(2.55, -50);
    expect(typeof z).toBe('number');
    expect(Number.isFinite(z)).toBe(true);
  });
});
