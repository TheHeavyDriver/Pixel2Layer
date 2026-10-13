'use client';

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
} from 'react';

import type { SceneGraph, SceneGraphElement } from '@pixel2layer/schema';
import {
  ActiveSelection,
  Canvas,
  Group,
  Point,
  type Object as FabricObject,
} from 'fabric';

import {
  canvasToScene,
  sceneToCanvas,
  type FabricWithMeta,
} from '@/lib/editor/scene-fabric';
import { computeContainViewport, computeWheelZoom } from '@/lib/editor/viewport';

export interface CanvasEditorHandle {
  selectByIds(ids: string[]): void;
  groupSelected(): void;
  groupByIds(ids: string[]): void;
  ungroupSelected(): void;
  duplicateSelected(): void;
  deleteSelected(): void;
  bringToFront(): void;
  sendToBack(): void;
  align(direction: 'left' | 'center' | 'right' | 'top' | 'middle' | 'bottom'): void;
  distribute(axis: 'horizontal' | 'vertical'): void;
  fitToScreen(): void;
  zoom(delta: number): void;
  addElement(element: SceneGraphElement): void;
  readScene(): SceneGraph;
}

interface CanvasEditorProps {
  scene: SceneGraph;
  onChange: (scene: SceneGraph) => void;
  onSelectionChange: (ids: string[]) => void;
  className?: string;
}

const ZOOM_STEPS = [0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4];

/**
 * Live Fabric.js canvas bound to a scene graph. Owns object manipulation and
 * emits `onChange` with a freshly read-back scene after any canvas mutation.
 */
export const CanvasEditor = forwardRef<CanvasEditorHandle, CanvasEditorProps>(
  function CanvasEditor({ scene, onChange, onSelectionChange, className }, ref) {
    const canvasRef = useRef<HTMLCanvasElement | null>(null);
    const containerRef = useRef<HTMLDivElement | null>(null);
    const fabricRef = useRef<Canvas | null>(null);
    const lastSyncedRef = useRef<string>('');
    // True once the user zooms/pans manually (wheel, toolbar). While set, a
    // container resize keeps the user's viewport instead of snapping back to
    // fit — otherwise Ctrl+wheel zoom would be instantly cancelled by the
    // refit. Cleared by Fit-to-screen and by every fresh scene sync (import).
    const manualZoomRef = useRef(false);
    const sceneRef = useRef<SceneGraph>(scene);
    const onChangeRef = useRef(onChange);
    const onSelectionChangeRef = useRef(onSelectionChange);
    onChangeRef.current = onChange;
    onSelectionChangeRef.current = onSelectionChange;

    // create canvas once
    useEffect(() => {
      if (!canvasRef.current) return;
      const canvas = new Canvas(canvasRef.current, {
        preserveObjectStacking: true,
        selection: true,
        width: scene.canvas.width,
        height: scene.canvas.height,
      });
      canvas.selectionColor = 'rgba(108,142,255,0.14)';
      canvas.selectionBorderColor = '#6C8EFF';
      canvas.selectionLineWidth = 1;
      fabricRef.current = canvas;
      // Fresh canvas instance → force the next scene sync to actually run
      // (the previous instance may have already stamped `lastSyncedRef`).
      lastSyncedRef.current = '';
      return () => {
        // Detach first so any in-flight async sync bails out on the identity
        // check below instead of touching a disposed canvas.
        fabricRef.current = null;
        canvas.dispose();
      };
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const getViewSize = useCallback(
      (canvas: Canvas) => {
        const container = containerRef.current;
        const rect = container?.getBoundingClientRect();
        const width =
          (rect && rect.width > 0 ? rect.width : 0) ||
          container?.clientWidth ||
          canvas.getElement()?.parentElement?.clientWidth ||
          800;
        const height =
          (rect && rect.height > 0 ? rect.height : 0) ||
          container?.clientHeight ||
          canvas.getElement()?.parentElement?.clientHeight ||
          600;
        return { width, height };
      },
      [],
    );

    const fitToViewport = useCallback((canvas: Canvas) => {
      // `getElement()` reads `canvas.elements.lower.el`, which is undefined
      // once the canvas has been disposed (unmount / remount / HMR). Only
      // fit the instance that is currently live.
      if (fabricRef.current !== canvas) return;
      // The Fabric viewport fills the editing area; the scene (uploaded
      // image) is scaled to fit inside it. Scene units stay 1:1 — only the
      // viewport transform zooms — so editing/export coordinates are exact.
      const { width: viewW, height: viewH } = getViewSize(canvas);
      const sceneW = sceneRef.current.canvas.width || 900;
      const sceneH = sceneRef.current.canvas.height || 600;
      canvas.setDimensions({ width: viewW, height: viewH });
      // Contain-fit: uniform scale on both axes so the whole scene is always
      // visible — never cropped, cut, or stretched. Aspect ratio is preserved
      // by construction (single zoom, centered letterbox, no cover-crop).
      const { zoom, tx, ty } = computeContainViewport(viewW, viewH, sceneW, sceneH);
      // Guard only against degenerate values; never clamp the fit itself —
      // clamping would re-introduce cropping on very large/small uploads.
      const safeZoom = Number.isFinite(zoom) && zoom > 0 ? Math.min(100, Math.max(0.001, zoom)) : 1;
      canvas.setViewportTransform([safeZoom, 0, 0, safeZoom, tx, ty]);
      canvas.requestRenderAll();
      manualZoomRef.current = false;
    }, [getViewSize]);

    const syncFromScene = useCallback(
      async (next: SceneGraph) => {
        const canvas = fabricRef.current;
        if (!canvas) return;
        sceneRef.current = next;
        const key = JSON.stringify(next);
        if (key === lastSyncedRef.current) return;
        lastSyncedRef.current = key;
        const container = containerRef.current;
        const viewport =
          container && container.clientWidth > 0 && container.clientHeight > 0
            ? { width: container.clientWidth, height: container.clientHeight }
            : undefined;
        await sceneToCanvas(next, canvas, () => fabricRef.current === canvas, viewport);
        if (fabricRef.current !== canvas) return; // disposed while loading
        fitToViewport(canvas);
      },
      [fitToViewport],
    );

    const readAndSync = useCallback(() => {
      const canvas = fabricRef.current;
      if (!canvas) return;
      sceneRef.current = canvasToScene(canvas, sceneRef.current);
      lastSyncedRef.current = JSON.stringify(sceneRef.current);
      onChangeRef.current(sceneRef.current);
    }, []);

    // wire selection + mutation events
    useEffect(() => {
      const canvas = fabricRef.current;
      if (!canvas) return;

      const reportSelection = () => {
        const objs = (canvas.getActiveObjects?.() ?? []) as FabricWithMeta[];
        const ids = objs
          .map((o) => o.p2lId)
          .filter((id): id is string => Boolean(id));
        onSelectionChangeRef.current(ids);
      };
      const handleModified = () => {
        // wait for fabric internal state to settle before reading geometry
        setTimeout(readAndSync, 0);
      };
      // Ctrl/Cmd + wheel zooms the canvas around the cursor (Figma-style);
      // plain wheel pans. preventDefault keeps the browser from page-zooming
      // or scrolling instead — only the viewport transform changes, so scene
      // geometry (and aspect ratio) is never distorted.
      const handleWheel = (opt: { e: WheelEvent }) => {
        const live = fabricRef.current;
        if (!live || fabricRef.current !== canvas) return;
        const e = opt.e;
        e.preventDefault();
        if (e.ctrlKey || e.metaKey) {
          const zoom = computeWheelZoom(live.getZoom(), e.deltaY);
          live.zoomToPoint(new Point(e.offsetX, e.offsetY), zoom);
        } else {
          const vpt = live.viewportTransform;
          if (!vpt) return;
          const dx = e.shiftKey ? e.deltaY : e.deltaX || 0;
          const dy = e.shiftKey ? 0 : e.deltaY;
          vpt[4] -= dx;
          vpt[5] -= dy;
          live.requestRenderAll();
        }
        manualZoomRef.current = true;
      };

      canvas.on('selection:created', reportSelection);
      canvas.on('selection:updated', reportSelection);
      canvas.on('selection:cleared', () => onSelectionChangeRef.current([]));
      canvas.on('object:modified', handleModified);
      canvas.on('mouse:wheel', handleWheel);
      return () => {
        canvas.off('selection:created', reportSelection);
        canvas.off('selection:updated', reportSelection);
        canvas.off('selection:cleared');
        canvas.off('object:modified', handleModified);
        canvas.off('mouse:wheel', handleWheel);
      };
    }, []);

    // react to external scene changes (undo/redo, property edits)
    useEffect(() => {
      syncFromScene(scene);
    }, [scene, syncFromScene]);

    // Refit when the editing area resizes (window resize, panel toggles).
    // Without this the fitted zoom goes stale and the scene overflows/crops.
    // A manual user zoom is preserved across resizes — only the canvas
    // element is matched to the container, the viewport transform is kept.
    useEffect(() => {
      const container = containerRef.current;
      const canvas = fabricRef.current;
      if (!container || !canvas) return;
      // The container may measure 0 on first mount; refit on the next frame.
      const raf = requestAnimationFrame(() => {
        const live = fabricRef.current;
        if (live && !manualZoomRef.current) fitToViewport(live);
      });
      if (typeof ResizeObserver === 'undefined') return () => cancelAnimationFrame(raf);
      const ro = new ResizeObserver(() => {
        const live = fabricRef.current;
        if (!live || fabricRef.current !== live) return;
        if (manualZoomRef.current) {
          const { width, height } = getViewSize(live);
          live.setDimensions({ width, height });
          live.requestRenderAll();
        } else {
          fitToViewport(live);
        }
      });
      ro.observe(container);
      return () => {
        cancelAnimationFrame(raf);
        ro.disconnect();
      };
    }, [fitToViewport, getViewSize]);

    useImperativeHandle(
      ref,
      () => {
        const activeObjects = () => {
          const canvas = fabricRef.current;
          if (!canvas) return [];
          return (
            canvas.getActiveObjects?.() ??
            (canvas.getActiveObject() ? [canvas.getActiveObject()] : [])
          );
        };

        return {
          selectByIds(ids: string[]) {
            const canvas = fabricRef.current;
            if (!canvas) return;
            canvas.discardActiveObject();
            const objs = canvas.getObjects().filter((o) => {
              const item = o as FabricWithMeta;
              return ids.includes(item.p2lId ?? '');
            });
            if (objs.length === 1) {
              canvas.setActiveObject(objs[0]);
            } else if (objs.length > 1) {
              canvas.setActiveObject(new ActiveSelection(objs, { canvas }));
            }
            canvas.requestRenderAll();
          },

          groupSelected() {
            const canvas = fabricRef.current;
            if (!canvas) return;
            const active = activeObjects();
            if (active.length < 2) return;
            canvas.remove(...active);
            const group = new Group(active, { canvas });
            canvas.add(group);
            canvas.setActiveObject(group);
            canvas.requestRenderAll();
            readAndSync();
          },

          groupByIds(ids: string[]) {
            const canvas = fabricRef.current;
            if (!canvas) return;
            const objs = canvas.getObjects().filter((o) => {
              const item = o as FabricWithMeta;
              return ids.includes(item.p2lId ?? '');
            });
            if (objs.length < 2) return;
            canvas.discardActiveObject();
            canvas.remove(...objs);
            const group = new Group(objs, { canvas });
            canvas.add(group);
            canvas.requestRenderAll();
            readAndSync();
          },

          ungroupSelected() {
            const canvas = fabricRef.current;
            if (!canvas) return;
            const active = canvas.getActiveObject();
            if (!active || active.type !== 'group') return;
            const group = active as Group;
            const kids = [...group.getObjects()];
            group.removeAll();
            canvas.remove(group);
            canvas.add(...kids);
            canvas.discardActiveObject();
            canvas.requestRenderAll();
            readAndSync();
          },

          duplicateSelected() {
            const canvas = fabricRef.current;
            if (!canvas) return;
            const active = activeObjects();
            if (active.length === 0) return;
            (async () => {
              for (const obj of active) {
                const clone = await obj.clone();
                clone.set({
                  left: (clone.left ?? 0) + 16,
                  top: (clone.top ?? 0) + 16,
                });
                canvas.add(clone);
              }
              canvas.discardActiveObject();
              canvas.requestRenderAll();
              readAndSync();
            })();
          },

          deleteSelected() {
            const canvas = fabricRef.current;
            if (!canvas) return;
            const active = activeObjects();
            if (active.length === 0) return;
            canvas.remove(...active);
            canvas.discardActiveObject();
            canvas.requestRenderAll();
            readAndSync();
          },

          bringToFront() {
            moveSelection('front');
          },
          sendToBack() {
            moveSelection('back');
          },

          align(direction) {
            alignObjects('align', direction);
          },

          distribute(axis) {
            alignObjects('distribute', axis);
          },

          fitToScreen() {
            const canvas = fabricRef.current;
            if (canvas) fitToViewport(canvas);
          },

          zoom(delta: number) {
            const canvas = fabricRef.current;
            if (!canvas) return;
            const zoom = stepZoom(canvas.getZoom(), delta);
            const container = containerRef.current;
            const cx = (container?.clientWidth || 800) / 2;
            const cy = (container?.clientHeight || 600) / 2;
            canvas.zoomToPoint(new Point(cx, cy), zoom);
            manualZoomRef.current = true;
            canvas.requestRenderAll();
          },

          addElement(element: SceneGraphElement) {
            const canvas = fabricRef.current;
            if (!canvas) return;
            sceneRef.current = {
              ...sceneRef.current,
              layers: [...sceneRef.current.layers, element],
            };
            const container = containerRef.current;
            const viewport =
              container && container.clientWidth > 0 && container.clientHeight > 0
                ? { width: container.clientWidth, height: container.clientHeight }
                : undefined;
            sceneToCanvas(sceneRef.current, canvas, () => fabricRef.current === canvas, viewport).then(
              () => {
                if (fabricRef.current !== canvas) return;
                fitToViewport(canvas);
                readAndSync();
              },
            );
          },

          readScene() {
            const canvas = fabricRef.current;
            if (!canvas) return sceneRef.current;
            return canvasToScene(canvas, sceneRef.current);
          },
        };

        function moveSelection(kind: 'front' | 'back') {
          const canvas = fabricRef.current;
          if (!canvas) return;
          const objs = canvas.getObjects() as FabricWithMeta[];
          const active = activeObjects();
          if (active.length === 0) return;
          const ids = new Set(active.map((o) => (o as FabricWithMeta).p2lId).filter(Boolean));
          if (kind === 'front') {
            const rev = [...objs].reverse();
            rev.forEach((o) => {
              if (ids.has(o.p2lId as string)) canvas.moveObjectTo(o, canvas.getObjects().length - 1);
            });
          } else {
            objs.forEach((o, i) => {
              if (ids.has(o.p2lId as string)) canvas.moveObjectTo(o, i);
            });
          }
          canvas.discardActiveObject();
          canvas.requestRenderAll();
          readAndSync();
        }

        function alignObjects(
          mode: 'align',
          dir: 'left' | 'center' | 'right' | 'top' | 'middle' | 'bottom',
        ): void;
        function alignObjects(mode: 'distribute', axis: 'horizontal' | 'vertical'): void;
        function alignObjects(
          mode: 'align' | 'distribute',
          arg: 'left' | 'center' | 'right' | 'top' | 'middle' | 'bottom' | 'horizontal' | 'vertical',
        ) {
          const canvas = fabricRef.current;
          if (!canvas) return;
          const objs = activeObjects() as FabricObject[];
          if (objs.length < 2) return;

          const bounds = objs.map((o) => o.getBoundingRect());

          if (mode === 'align') {
            const dir = arg as 'left' | 'center' | 'right' | 'top' | 'middle' | 'bottom';
            const minL = Math.min(...bounds.map((b) => b.left));
            const maxR = Math.max(...bounds.map((b) => b.left + b.width));
            const minT = Math.min(...bounds.map((b) => b.top));
            const maxB = Math.max(...bounds.map((b) => b.top + b.height));
            objs.forEach((o, i) => {
              const b = bounds[i];
              let x = o.left;
              let y = o.top;
              if (dir === 'left') x = b.left - (o.left ?? 0) + minL;
              if (dir === 'right') x = b.left - (o.left ?? 0) + (maxR - b.width);
              if (dir === 'center') x = b.left - (o.left ?? 0) + (minL + maxR) / 2 - b.width / 2;
              if (dir === 'top') y = b.top - (o.top ?? 0) + minT;
              if (dir === 'bottom') y = b.top - (o.top ?? 0) + (maxB - b.height);
              if (dir === 'middle') y = b.top - (o.top ?? 0) + (minT + maxB) / 2 - b.height / 2;
              o.setXY(new Point(x, y));
            });
          } else {
            const axis = arg as 'horizontal' | 'vertical';
            if (objs.length < 3) return;
            const sorted = [...objs]
              .map((o, i) => ({ o, b: bounds[i], i }))
              .sort((a, c) =>
                axis === 'horizontal' ? a.b.left - c.b.left : a.b.top - c.b.top,
              );
            const first = sorted[0];
            const last = sorted[sorted.length - 1];
            const totalSpan =
              axis === 'horizontal'
                ? last.b.left - (first.b.left + first.b.width)
                : last.b.top - (first.b.top + first.b.height);
            const gap = totalSpan / (sorted.length - 1);
            sorted.forEach(({ o, b }, idx) => {
              if (idx === 0) return;
              let x = o.left ?? 0;
              let y = o.top ?? 0;
              if (axis === 'horizontal') {
                x = first.b.left + first.b.width + gap * idx;
                void b;
              } else {
                y = first.b.top + first.b.height + gap * idx;
              }
              o.setXY(new Point(x, y));
            });
          }
          canvas.requestRenderAll();
          readAndSync();
        }
      },
      [fitToViewport, readAndSync],
    );

    return (
      <div
        ref={containerRef}
        className={`flex h-full w-full items-center justify-center overflow-hidden ${className ?? ''}`}
      >
        <canvas
          ref={canvasRef}
          data-testid="editor-canvas"
          className="block shrink-0"
        />
      </div>
    );
  },
);

function stepZoom(current: number, delta: number): number {
  // Step to the next/previous rung in the direction of `delta`, so repeated
  // +/- presses always move. (The old `nearestStep(current + delta)` could
  // stick on the same rung when the fitted zoom sits between steps.)
  if (delta > 0) {
    for (const step of ZOOM_STEPS) {
      if (step > current + 1e-9) return step;
    }
    return ZOOM_STEPS[ZOOM_STEPS.length - 1];
  }
  for (let i = ZOOM_STEPS.length - 1; i >= 0; i--) {
    if (ZOOM_STEPS[i] < current - 1e-9) return ZOOM_STEPS[i];
  }
  return ZOOM_STEPS[0];
}