import { describe, expect, it } from 'vitest';
import { renderHook, act } from '@testing-library/react';

import { useSceneHistory } from '@/lib/editor/use-scene-history';
import { makeScene } from '@/test/fixtures';

describe('useSceneHistory', () => {
  it('commits a change and enables undo', () => {
    const { result } = renderHook(() => useSceneHistory(makeScene()));
    const scene = makeScene();
    scene.layers[0].fill = '#111111';

    act(() => result.current.commit(scene));

    expect(result.current.canUndo).toBe(true);
    expect(result.current.canRedo).toBe(false);
    expect(result.current.scene.layers[0].fill).toBe('#111111');
  });

  it('undo restores the previous state and pushes onto the redo stack', () => {
    const initial = makeScene();
    const { result } = renderHook(() => useSceneHistory(initial));

    const next = makeScene();
    next.layers[0].fill = '#222222';
    act(() => result.current.commit(next));

    let prev: unknown;
    act(() => {
      prev = result.current.undo();
    });

    expect(prev).not.toBeNull();
    expect(result.current.scene.layers[0].fill).toBe('#FF5733');
    expect(result.current.canUndo).toBe(false);
    expect(result.current.canRedo).toBe(true);
  });

  it('redo replays the undone state', () => {
    const { result } = renderHook(() => useSceneHistory(makeScene()));

    const next = makeScene();
    next.layers[0].fill = '#333333';
    act(() => result.current.commit(next));
    act(() => result.current.undo());
    act(() => result.current.redo());

    expect(result.current.scene.layers[0].fill).toBe('#333333');
    expect(result.current.canUndo).toBe(true);
    expect(result.current.canRedo).toBe(false);
  });

  it('dedupes identical commits (same layers payload)', () => {
    const { result } = renderHook(() => useSceneHistory(makeScene()));

    const scene = result.current.scene;
    act(() => result.current.commit(cloneScene(scene)));

    expect(result.current.canUndo).toBe(false);
  });

  it('clears the redo stack when a new commit lands after an undo', () => {
    const { result } = renderHook(() => useSceneHistory(makeScene()));

    const a = makeScene();
    a.layers[0].fill = '#a1';
    act(() => result.current.commit(a));

    const b = makeScene();
    b.layers[0].fill = '#b2';
    act(() => result.current.commit(b));

    act(() => result.current.undo());
    expect(result.current.canRedo).toBe(true);

    const c = makeScene();
    c.layers[0].fill = '#c3';
    act(() => result.current.commit(c));

    expect(result.current.canRedo).toBe(false);
  });

  it('reset clears history and sets a fresh present', () => {
    const { result } = renderHook(() => useSceneHistory(makeScene()));

    const a = makeScene();
    a.layers[0].fill = '#q1';
    act(() => result.current.commit(a));
    expect(result.current.canUndo).toBe(true);

    act(() => result.current.reset(makeScene()));
    expect(result.current.canUndo).toBe(false);
    expect(result.current.canRedo).toBe(false);
  });
});

function cloneScene(s: ReturnType<typeof makeScene>) {
  return JSON.parse(JSON.stringify(s)) as ReturnType<typeof makeScene>;
}