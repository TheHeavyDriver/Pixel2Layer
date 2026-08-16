import { useCallback, useMemo, useRef, useState } from 'react';

import type { SceneGraph } from '@pixel2layer/schema';

export const MAX_HISTORY_DEPTH = 100;

interface HistoryFrame {
  scene: SceneGraph;
}

function clone(scene: SceneGraph): SceneGraph {
  return JSON.parse(JSON.stringify(scene)) as SceneGraph;
}

/**
 * Snapshot-based undo/redo over the scene graph. Pushes `next` only when it
 * actually differs from the current head to avoid noise from same-state commits.
 */
export function useSceneHistory(initialScene: SceneGraph) {
  const pastRef = useRef<HistoryFrame[]>([]);
  const futureRef = useRef<HistoryFrame[]>([]);
  const [present, setPresent] = useState<SceneGraph>(() => clone(initialScene));

  const canUndo = pastRef.current.length > 0;
  const canRedo = futureRef.current.length > 0;

  const commit = useCallback((next: SceneGraph) => {
    setPresent((current) => {
      if (JSON.stringify(current.layers) === JSON.stringify(next.layers)) return current;
      pastRef.current.push({ scene: clone(current) });
      if (pastRef.current.length > MAX_HISTORY_DEPTH) pastRef.current.shift();
      futureRef.current = [];
      return clone(next);
    });
  }, []);

  const forceCommit = useCallback((next: SceneGraph) => {
    setPresent(clone(next));
  }, []);

  const undo = useCallback(() => {
    const frame = pastRef.current.pop();
    if (!frame) return null;
    futureRef.current.push({ scene: clone(present) });
    const prev = frame.scene;
    setPresent(prev);
    return prev;
  }, [present]);

  const redo = useCallback(() => {
    const frame = futureRef.current.pop();
    if (!frame) return null;
    pastRef.current.push({ scene: clone(present) });
    setPresent(frame.scene);
    return frame.scene;
  }, [present]);

  const reset = useCallback(
    (scene: SceneGraph) => {
      pastRef.current = [];
      futureRef.current = [];
      setPresent(clone(scene));
    },
    [],
  );

  return useMemo(
    () => ({
      scene: present,
      setScene: forceCommit,
      commit,
      undo,
      redo,
      reset,
      canUndo,
      canRedo,
    }),
    [present, commit, undo, redo, reset, forceCommit, canUndo, canRedo],
  );
}