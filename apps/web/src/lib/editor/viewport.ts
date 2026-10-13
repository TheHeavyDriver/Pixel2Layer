/**
 * Viewport math for fitting a scene inside the editing area.
 *
 * Contract (user-visible):
 *  1. The whole scene always fits inside the editable window.
 *  2. Nothing is cropped, cut, or stretched — aspect ratio is preserved
 *     exactly (uniform "contain" scale, no independent X/Y scaling).
 */

/** Result of {@link computeContainViewport}: a uniform zoom + centering offset. */
export interface ContainViewport {
  /** Uniform scale applied to both axes (aspect preserved by construction). */
  zoom: number;
  /** Viewport translation X (centers the scene horizontally). */
  tx: number;
  /** Viewport translation Y (centers the scene vertically). */
  ty: number;
}

/**
 * Compute a contain-fit viewport: the largest uniform scale that keeps the
 * entire scene visible inside the view, centered on both axes.
 *
 * - Uses `Math.min` (contain), never `Math.max` (cover would crop).
 * - Single zoom for both axes, so aspect ratio cannot change.
 * - Degenerate/zero sizes fall back to identity instead of NaN/Infinity.
 */
export function computeContainViewport(
  viewW: number,
  viewH: number,
  sceneW: number,
  sceneH: number,
): ContainViewport {
  if (
    !Number.isFinite(viewW) ||
    !Number.isFinite(viewH) ||
    !Number.isFinite(sceneW) ||
    !Number.isFinite(sceneH) ||
    viewW <= 0 ||
    viewH <= 0 ||
    sceneW <= 0 ||
    sceneH <= 0
  ) {
    return { zoom: 1, tx: 0, ty: 0 };
  }
  const zoom = Math.min(viewW / sceneW, viewH / sceneH);
  const tx = (viewW - sceneW * zoom) / 2;
  const ty = (viewH - sceneH * zoom) / 2;
  return { zoom, tx, ty };
}

/** Bounds for manual canvas zoom (toolbar +/−, Ctrl+wheel). */
export const MIN_ZOOM = 0.01;
export const MAX_ZOOM = 100;

/**
 * Smooth exponential wheel-zoom step: wheel-up (negative deltaY) zooms in,
 * wheel-down zooms out. Pure + clamped, so it is unit-testable; the canvas
 * component applies it via `zoomToPoint` at the cursor (uniform on both
 * axes, so aspect ratio is never distorted).
 */
export function computeWheelZoom(currentZoom: number, deltaY: number): number {
  const base = Number.isFinite(currentZoom) && currentZoom > 0 ? currentZoom : 1;
  const next = base * Math.pow(0.999, deltaY);
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, next));
}
