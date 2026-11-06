'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

import type { SceneGraph } from '@pixel2layer/schema';

import { exportScene, importProjectP2l, saveProjectP2l, suggestGroups } from '@/lib/api';
import { extractErrorMessage } from '@/lib/error-utils';
import type { CanvasEditorHandle } from '@/components/editor/canvas-editor';
import type { useSceneHistory } from '@/lib/editor/use-scene-history';
import { CloudSaveControl } from './cloud-save-control';
import { ShareControl } from './share-control';

interface ToolbarProps {
  scene: SceneGraph;
  onChange: (s: SceneGraph) => void;
  onUndo: () => SceneGraph | null;
  onRedo: () => SceneGraph | null;
  history: ReturnType<typeof useSceneHistory>;
  editorRef: React.RefObject<CanvasEditorHandle | null>;
  activeProjectId: string | null;
  projectName: string;
  shared: { token: string; permission: 'view' | 'edit' } | null;
  onProjectChange: (id: string, name: string) => void;
  onRestoreScene: (scene: SceneGraph) => void;
  readScene: () => Record<string, unknown>;
}

export function Toolbar({
  scene,
  onChange,
  onUndo,
  onRedo,
  history,
  editorRef,
  activeProjectId,
  projectName,
  shared,
  onProjectChange,
  onRestoreScene,
  readScene,
}: ToolbarProps) {
  const canUndo = history.canUndo;
  const canRedo = history.canRedo;
  const router = useRouter();
  const [exporting, setExporting] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  async function handleExport(format: 'png' | 'jpg' | 'svg' | 'pdf') {
    setExportError(null);
    setExporting(format);
    try {
      const { exportScene } = await import('@/lib/api');
      const live = editorRef.current?.readScene() ?? scene;
      const blob = await exportScene({ format, canvas: live.canvas, layers: live.layers, confidence: live.confidence, overallConfidence: live.overallConfidence });
      triggerDownload(blob, `design.${format}`);
    } catch (e) {
      setExportError(extractErrorMessage(e, 'Export failed.'));
    } finally {
      setExporting(null);
    }
  }

  async function handleSave() {
    setExportError(null);
    setExporting('p2l');
    try {
      const { saveProjectP2l } = await import('@/lib/api');
      const live = editorRef.current?.readScene() ?? scene;
      const blob = await saveProjectP2l(live, 'design');
      triggerDownload(blob, 'design.p2l');
    } catch (e) {
      setExportError(extractErrorMessage(e, 'Save failed.'));
    } finally {
      setExporting(null);
    }
  }

  async function handleSaveAsTemplate() {
    setExportError(null);
    setExporting('template');
    try {
      const { createTemplate, getToken } = await import('@/lib/api');
      if (!getToken()) {
        router.push(`/login?redirect=${encodeURIComponent(window.location.href)}`);
        return;
      }
      const name = window.prompt('Name this template', projectName);
      if (!name?.trim()) return;
      const live = editorRef.current?.readScene() ?? scene;
      await createTemplate(name.trim(), live as unknown as Record<string, unknown>);
      setExportError('Saved as template');
    } catch (e) {
      setExportError(extractErrorMessage(e, 'Save failed.'));
    } finally {
      setExporting(null);
    }
  }

  const btn =
    'flex h-7 items-center justify-center gap-1 rounded-[8px] px-2 text-[12px] font-medium text-secondary transition-colors hover:bg-raised disabled:opacity-40';

  return (
    <div className="flex h-[44px] items-center gap-1 border-b border-bordered bg-surface px-3">
      <span className="flex h-[22px] w-[22px] items-center justify-center rounded-[4px] bg-accent" aria-hidden />
      <span className="mr-2 hidden text-[13px] font-semibold tracking-[-0.01em] lg:inline">
        Pixel2Layer
      </span>
      <div className="h-5 w-px bg-bordered" />
      <button
        type="button"
        className={btn}
        onClick={() => router.push('/dashboard')}
        title="My projects"
        data-testid="dashboard-btn"
      >
        Dashboard
      </button>
      <div className="h-5 w-px bg-bordered" />
      <button type="button" className={btn} onClick={() => onUndo()} disabled={!canUndo} title="Undo (Ctrl+Z)" data-testid="undo-btn">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 14 4 9l5-5" /><path d="M4 9h10a5 5 0 0 1 0 10h-3" /></svg>
      </button>
      <button type="button" className={btn} onClick={() => onRedo()} disabled={!canRedo} title="Redo (Ctrl+Shift+Z)" data-testid="redo-btn">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m15 14 5-5-5-5" /><path d="M20 9H10a5 5 0 0 0 0 10h3" /></svg>
      </button>
      <div className="h-5 w-px bg-bordered" />
      <button
        type="button"
        className={btn}
        onClick={() => editorRef.current?.groupSelected()}
        title="Group (Ctrl+G)"
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /><path d="M6.5 10v4a4 4 0 0 0 4 4h4" /></svg>
      </button>
      <button
        type="button"
        className={btn}
        onClick={() => {
          void import('@/lib/api').then(async ({ suggestGroups }) => {
            try {
              const live = editorRef.current?.readScene() ?? scene;
              const groups = await suggestGroups({
                canvas: live.canvas,
                layers: live.layers as unknown[],
              });
              const groupable = groups
                .map((g) => g.elementIds)
                .find((ids) => ids.length >= 2);
              if (!groupable) {
                setExportError('No suggested groups with 2+ layers');
                return;
              }
              editorRef.current?.groupByIds(groupable);
              setExportError(null);
            } catch (e) {
              setExportError(extractErrorMessage(e, 'Smart group failed.'));
            }
          });
        }}
        title="Group layers into the first suggested layout group"
        data-testid="smart-group-btn"
      >
        Smart group
      </button>
      <div className="h-5 w-px bg-bordered" />
      <button
        type="button"
        className={btn}
        onClick={() => editorRef.current?.ungroupSelected()}
        title="Ungroup (Ctrl+Shift+G)"
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /><path d="M10 10h1a4 4 0 0 1 4 4v1" /></svg>
      </button>
      <button
        type="button"
        className={btn}
        onClick={() => editorRef.current?.duplicateSelected()}
        title="Duplicate (Ctrl+D)"
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="12" height="12" rx="2" /><path d="M5 15V5a2 2 0 0 1 2-2h10" /></svg>
      </button>
      <button
        type="button"
        className={btn}
        onClick={() => editorRef.current?.deleteSelected()}
        title="Delete (Del)"
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 6h18" /><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" /></svg>
      </button>
      <div className="h-5 w-px bg-bordered" />
      {(['left', 'center', 'right', 'top', 'middle', 'bottom'] as const).map((d) => (
        <button
          key={d}
          type="button"
          className={btn}
          onClick={() => editorRef.current?.align(d)}
          title={`Align ${d}`}
          style={{ textTransform: 'capitalize', fontSize: '11px' }}
        >
          {d}
        </button>
      ))}
      <div className="h-5 w-px bg-bordered" />
      <div className="flex flex-1" />
      <button type="button" className={btn} onClick={() => editorRef.current?.zoom(-0.25)} title="Zoom out">−</button>
      <button type="button" className={btn} onClick={() => editorRef.current?.fitToScreen()} title="Fit to screen">Fit</button>
      <button type="button" className={btn} onClick={() => editorRef.current?.zoom(0.25)} title="Zoom in">+</button>
      <div className="h-5 w-px bg-bordered" />
      <button
        type="button"
        className={btn}
        onClick={() => void import('@/lib/api').then(async ({ importProjectP2l }) => {
          try {
            const file = await pickFile();
            if (!file) return;
            const loaded = (await importProjectP2l(file)) as unknown as SceneGraph;
            onChange(loaded);
          } catch (e) {
            setExportError(extractErrorMessage(e, 'Import failed.'));
          }
        })}
        title="Open .p2l file"
      >
        Open
      </button>
      <button type="button" className={btn} onClick={() => void handleSave()} disabled={exporting === 'p2l'} title="Save as .p2l">
        {exporting === 'p2l' ? 'Saving…' : 'Save .p2l'}
      </button>
      <div className="h-5 w-px bg-bordered" />
      <CloudSaveControl
        activeProjectId={activeProjectId}
        projectName={projectName}
        shared={shared}
        onProjectChange={onProjectChange}
        onRestoreScene={onRestoreScene}
        readScene={readScene}
      />
      {!shared && (
        <>
          <div className="h-5 w-px bg-bordered" />
          <button
            type="button"
            className={btn}
            onClick={() => void handleSaveAsTemplate()}
            disabled={exporting === 'template'}
            title="Save this design as a reusable template"
            data-testid="save-template-btn"
          >
            {exporting === 'template' ? 'Saving…' : 'Save as template'}
          </button>
          <ShareControl
            activeProjectId={activeProjectId}
            onProjectChange={onProjectChange}
            readScene={readScene}
          />
        </>
      )}
      <div className="h-5 w-px bg-bordered" />
      {(['png', 'jpg', 'svg', 'pdf'] as const).map((f) => (
        <button
          key={f}
          type="button"
          className={`${btn} ${f === 'png' ? 'bg-accent text-white hover:bg-accent-hover' : ''}`}
          onClick={() => void handleExport(f)}
          disabled={exporting !== null}
          title={`Export ${f.toUpperCase()}`}
        >
          {exporting === f ? '…' : f.toUpperCase()}
        </button>
      ))}
      {exportError && (
        <span className="ml-2 text-[12px] text-warning" role="alert">
          {exportError}
        </span>
      )}
    </div>
  );
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function pickFile(): Promise<File | null> {
  return new Promise((resolve) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.p2l,application/json';
    input.onchange = () => resolve(input.files?.[0] ?? null);
    input.oncancel = () => resolve(null);
    input.click();
  });
}
