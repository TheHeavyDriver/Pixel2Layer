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
    const fabricRef = useRef<Canvas | null>(null);
    const lastSyncedRef = useRef<string>('');
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

    const fitToViewport = useCallback((canvas: Canvas) => {
      // `getElement()` reads `canvas.elements.lower.el`, which is undefined
      // once the canvas has been disposed (unmount / remount / HMR). Only
      // fit the instance that is currently live.
      if (fabricRef.current !== canvas) return;
      const el = canvas.getElement();
      const viewW = el.clientWidth || 800;
      const viewH = el.clientHeight || 600;
      const scale = Math.min(
        (viewW - 32) / (canvas.width || 1),
        (viewH - 32) / (canvas.height || 1),
        1,
      );
      canvas.absolutePan(new Point(0, 0));
      canvas.setZoom(Math.max(0.25, scale));
      const cx = (viewW - (canvas.width || 1) * canvas.getZoom()) / 2;
      const cy = (viewH - (canvas.height || 1) * canvas.getZoom()) / 2;
      canvas.absolutePan(new Point(cx, cy));
      canvas.requestRenderAll();
    }, []);

    const syncFromScene = useCallback(
      async (next: SceneGraph) => {
        const canvas = fabricRef.current;
        if (!canvas) return;
        sceneRef.current = next;
        const key = JSON.stringify(next);
        if (key === lastSyncedRef.current) return;
        lastSyncedRef.current = key;
        await sceneToCanvas(next, canvas, () => fabricRef.current === canvas);
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

      canvas.on('selection:created', reportSelection);
      canvas.on('selection:updated', reportSelection);
      canvas.on('selection:cleared', () => onSelectionChangeRef.current([]));
      canvas.on('object:modified', handleModified);
      return () => {
        canvas.off('selection:created', reportSelection);
        canvas.off('selection:updated', reportSelection);
        canvas.off('selection:cleared');
        canvas.off('object:modified', handleModified);
      };
    }, []);

    // react to external scene changes (undo/redo, property edits)
    useEffect(() => {
      syncFromScene(scene);
    }, [scene, syncFromScene]);

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
            let zoom = nearestStep(canvas.getZoom() + delta);
            const el = canvas.getElement();
            const cx = el.clientWidth / 2;
            const cy = el.clientHeight / 2;
            canvas.zoomToPoint(new Point(cx, cy), zoom);
            canvas.requestRenderAll();
          },

          addElement(element: SceneGraphElement) {
            const canvas = fabricRef.current;
            if (!canvas) return;
            sceneRef.current = {
              ...sceneRef.current,
              layers: [...sceneRef.current.layers, element],
            };
            sceneToCanvas(sceneRef.current, canvas, () => fabricRef.current === canvas).then(
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
      <div className={`relative h-full w-full overflow-hidden ${className ?? ''}`}>
        <canvas
          ref={canvasRef}
          data-testid="editor-canvas"
          className="absolute inset-0"
        />
      </div>
    );
  },
);

function nearestStep(current: number): number {
  let best = ZOOM_STEPS[0];
  for (const step of ZOOM_STEPS) {
    if (Math.abs(step - current) < Math.abs(best - current)) best = step;
  }
  return best;
}