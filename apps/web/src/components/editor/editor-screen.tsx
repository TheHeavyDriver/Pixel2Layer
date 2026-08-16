'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';

import type { SceneGraph, SceneGraphElement } from '@pixel2layer/schema';

import { LayersPanel } from '@/components/editor/layers-panel';
import { PropertiesPanel } from '@/components/editor/properties-panel';
import {
  CanvasEditor,
  type CanvasEditorHandle,
} from '@/components/editor/canvas-editor';
import {
  createProject,
  createShare,
  getJob,
  getProject,
  getSharedProject,
  getToken,
  listShares,
  listVersions,
  restoreVersion,
  revokeShare,
  saveVersion,
  shareUrl,
  updateProject,
  updateSharedProject,
  type Share,
  type Version,
} from '@/lib/api';
import { useSceneHistory } from '@/lib/editor/use-scene-history';

interface EditorScreenProps {
  jobId: string | null;
  projectId?: string | null;
  shareToken?: string | null;
  templateId?: string | null;
}

function emptyScene(): SceneGraph {
  return {
    schemaVersion: 1,
    canvas: { width: 900, height: 600, background: '#FFFFFF' },
    layers: [],
    confidence: {},
    overallConfidence: 1,
    complexity: null,
  };
}

export function EditorScreen({ jobId, projectId, shareToken, templateId }: EditorScreenProps) {
  const router = useRouter();
  const [initialScene] = useState<SceneGraph>(() => emptyScene());
  const history = useSceneHistory(initialScene);
  const { scene, commit, undo, redo, reset } = history;
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(Boolean(jobId) || Boolean(projectId) || Boolean(shareToken) || Boolean(templateId));
  const [loadError, setLoadError] = useState<string | null>(null);
  const editorRef = useRef<CanvasEditorHandle | null>(null);

  // cloud project state (v0.3 persistence)
  const [activeProjectId, setActiveProjectId] = useState<string | null>(projectId ?? null);
  const [projectName, setProjectName] = useState('Untitled design');
  // shared-project state (v0.5)
  const [shared, setShared] = useState<{ token: string; permission: 'view' | 'edit' } | null>(
    null,
  );

  // load an existing project, finished job, shared design, or a template
  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!projectId && !jobId && !shareToken && !templateId) return;
      setLoading(true);
      setLoadError(null);
      try {
        if (shareToken) {
          const sharedProject = await getSharedProject(shareToken);
          if (cancelled) return;
          setShared({ token: shareToken, permission: sharedProject.permission });
          setProjectName(sharedProject.name);
          reset(sharedProject.sceneGraph as unknown as SceneGraph);
        } else if (projectId) {
          const project = await getProject(projectId);
          if (cancelled) return;
          setActiveProjectId(project.id);
          setProjectName(project.name);
          reset(project.sceneGraph as unknown as SceneGraph);
        } else if (templateId) {
          const { getTemplate } = await import('@/lib/api');
          const template = await getTemplate(templateId);
          if (cancelled) return;
          setProjectName(template.name);
          reset(template.sceneGraph as unknown as SceneGraph);
        } else {
          const job = await getJob(jobId!);
          if (cancelled) return;
          const result = job.result as { scene?: SceneGraph } | null;
          reset(result?.scene ? (result.scene as SceneGraph) : emptyScene());
        }
      } catch (e) {
        if (!cancelled) {
          setLoadError(e instanceof Error ? e.message : 'Failed to load design.');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [projectId, jobId, shareToken, templateId, reset]);

  // guard scene schema shape from older payloads
  const safeScene: SceneGraph = {
    ...scene,
    canvas: {
      width: scene.canvas.width || 900,
      height: scene.canvas.height || 600,
      background: scene.canvas.background ?? null,
    },
  };

  const updateElement = useCallback(
    (id: string, patch: Partial<SceneGraphElement>) => {
      commit({
        ...safeScene,
        layers: safeScene.layers.map((el) => (el.id === id ? ({ ...el, ...patch } as SceneGraphElement) : el)),
      });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [safeScene, commit],
  );

  const updateCanvas = useCallback(
    (patch: Partial<SceneGraph['canvas']>) => {
      commit({
        ...safeScene,
        canvas: { ...safeScene.canvas, ...patch },
      });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [safeScene, commit],
  );

  const duplicateById = useCallback(
    (id: string) => {
      const src = safeScene.layers.find((l) => l.id === id);
      if (!src) return;
      const copy = JSON.parse(JSON.stringify(src)) as SceneGraphElement;
      copy.id = `${src.type}_${Date.now().toString(36)}`;
      copy.name = `${src.name} copy`;
      commit({ ...safeScene, layers: [...safeScene.layers, copy] });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [safeScene, commit],
  );

  const deleteById = useCallback(
    (id: string) => {
      commit({ ...safeScene, layers: safeScene.layers.filter((l) => l.id !== id) });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [safeScene, commit],
  );

  const handleReorder = useCallback(
    (id: string, dir: 1 | -1) => {
      if (!id) return;
      const layers = [...safeScene.layers];
      const fromIdx = layers.findIndex((l) => l.id === id);
      const toIdx = fromIdx + dir;
      if (fromIdx < 0 || toIdx < 0 || toIdx >= layers.length) return;
      const [el] = layers.splice(fromIdx, 1);
      layers.splice(toIdx, 0, el);
      commit({ ...safeScene, layers });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [safeScene, commit],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.ctrlKey || e.metaKey;
      if (mod && e.key.toLowerCase() === 'z' && !e.shiftKey) {
        e.preventDefault();
        const prev = undo();
        if (prev) setSelectedIds([]);
      } else if (mod && e.key.toLowerCase() === 'z' && e.shiftKey) {
        e.preventDefault();
        const next = redo();
        if (next) setSelectedIds([]);
      } else if (mod && e.key.toLowerCase() === 'd') {
        e.preventDefault();
        editorRef.current?.duplicateSelected();
      } else if (e.key === 'Delete' || e.key === 'Backspace') {
        // ignore when typing in an input
        const target = e.target as HTMLElement | null;
        if (target && /INPUT|TEXTAREA|SELECT/.test(target.tagName)) return;
        e.preventDefault();
        editorRef.current?.deleteSelected();
      } else if (mod && e.key.toLowerCase() === 'g') {
        e.preventDefault();
        editorRef.current?.groupSelected();
      } else if (mod && e.shiftKey && e.key.toLowerCase() === 'g') {
        e.preventDefault();
        editorRef.current?.ungroupSelected();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [undo, redo]);

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-base">
        <div className="flex items-center gap-3 text-[13px] text-secondary">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          Loading design…
        </div>
      </main>
    );
  }

  if (loadError) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-base px-4">
        <h1 className="text-[20px] font-semibold">Could not open this design</h1>
        <p className="max-w-md text-center text-[13px] text-secondary">{loadError}</p>
        <button
          type="button"
          onClick={() => router.push('/')}
          className="h-9 rounded-[10px] bg-accent px-4 text-[13px] font-medium text-white transition-colors hover:bg-accent-hover"
        >
          Back to home
        </button>
      </main>
    );
  }

  return (
    <div
      className="flex h-screen flex-col bg-base"
      data-testid="editor-screen"
      style={{ height: '100dvh' }}
    >
      <Toolbar
        scene={safeScene}
        onChange={onToolbarChange}
        onUndo={undo}
        onRedo={redo}
        history={history}
        editorRef={editorRef}
        activeProjectId={activeProjectId}
        projectName={projectName}
        shared={shared}
        onProjectChange={(id, name) => {
          setActiveProjectId(id);
          setProjectName(name);
        }}
        onRestoreScene={reset}
        readScene={() => (editorRef.current?.readScene() ?? safeScene) as unknown as Record<string, unknown>}
      />
      <div className="flex min-h-0 flex-1">
        <LayersPanel
          layers={safeScene.layers}
          selectedIds={selectedIds}
          onSelect={(ids) => {
            setSelectedIds(ids);
            editorRef.current?.selectByIds(ids);
          }}
          onToggleVisible={(id) =>
            updateElement(id, { visible: !safeScene.layers.find((l) => l.id === id)?.visible })
          }
          onToggleLocked={(id) =>
            updateElement(id, { locked: !safeScene.layers.find((l) => l.id === id)?.locked })
          }
          onRename={(id, name) => updateElement(id, { name })}
          onDuplicate={duplicateById}
          onDelete={deleteById}
          onReorder={handleReorder}
        />

        <main
          className="flex min-w-0 flex-1 items-center justify-center overflow-hidden bg-canvas-drop p-4"
          style={{ background: '#111214' }}
        >
          <CanvasEditor
            ref={editorRef}
            scene={safeScene}
            onChange={(next) => {
              commit(next);
              const live = editorRef.current?.readScene();
              if (live) void live;
            }}
            onSelectionChange={setSelectedIds}
            className="h-full max-h-full w-full max-w-full"
          />
        </main>

        <PropertiesPanel
          scene={safeScene}
          selectedIds={selectedIds}
          onUpdateElement={updateElement}
          onUpdateCanvas={updateCanvas}
        />
      </div>
    </div>
  );

  function onToolbarChange(next: SceneGraph) {
    commit(next);
  }
}

// -- toolbar ----------------------------------------------------------------

function Toolbar({
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
}: {
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
}) {
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
      setExportError(e instanceof Error ? e.message : 'Export failed.');
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
      setExportError(e instanceof Error ? e.message : 'Save failed.');
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
      setExportError(e instanceof Error ? e.message : 'Save failed.');
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
              setExportError(e instanceof Error ? e.message : 'Smart group failed.');
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
            setExportError(e instanceof Error ? e.message : 'Import failed.');
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

// -- cloud project persistence ----------------------------------------------

function CloudSaveControl({
  activeProjectId,
  projectName,
  shared,
  onProjectChange,
  onRestoreScene,
  readScene,
}: {
  activeProjectId: string | null;
  projectName: string;
  shared: { token: string; permission: 'view' | 'edit' } | null;
  onProjectChange: (id: string, name: string) => void;
  onRestoreScene: (scene: SceneGraph) => void;
  readScene: () => Record<string, unknown>;
}) {
  const router = useRouter();
  const [versions, setVersions] = useState<Version[]>([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  const isViewOnly = shared?.permission === 'view';

  const refreshVersions = useCallback(async () => {
    if (!activeProjectId) {
      setVersions([]);
      return;
    }
    try {
      setVersions(await listVersions(activeProjectId));
    } catch {
      // non-fatal: the version list refreshes next open
    }
  }, [activeProjectId]);

  useEffect(() => {
    if (activeProjectId) void refreshVersions();
  }, [activeProjectId, refreshVersions]);

  async function ensureAuthed(): Promise<boolean> {
    if (getToken()) return true;
    router.push(`/login?redirect=${encodeURIComponent(window.location.href)}`);
    return false;
  }

  async function handleSaveProject() {
    if (!(await ensureAuthed())) return;
    setStatus(null);
    setBusy('save');
    try {
      const sceneGraph = readScene();
      if (shared) {
        const { updateSharedProject } = await import('@/lib/api');
        await updateSharedProject(shared.token, sceneGraph);
        setStatus('Saved changes');
      } else if (!activeProjectId) {
        const name = window.prompt('Name this project', projectName);
        if (!name?.trim()) return;
        const created = await createProject(name.trim(), sceneGraph);
        onProjectChange(created.id, created.name);
        router.replace(`/editor?project=${created.id}`, { scroll: false });
        await refreshVersions();
        setStatus('Project saved');
      } else {
        await updateProject(activeProjectId, { sceneGraph });
        setStatus('Saved');
      }
    } catch (e) {
      setStatus(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setBusy(null);
    }
  }

  async function handleSaveVersion() {
    setStatus(null);
    if (!activeProjectId) {
      setStatus('Save the project first');
      return;
    }
    setBusy('version');
    try {
      const version = await saveVersion(activeProjectId, readScene(), `Version ${versions.length + 1}`);
      setOpen(false);
      await refreshVersions();
      setStatus(`Version ${version.versionNo} saved`);
    } catch (e) {
      setStatus(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setBusy(null);
    }
  }

  async function handleRestore(versionNo: number) {
    if (!activeProjectId) return;
    if (!window.confirm(`Restore version ${versionNo}? The current canvas state will be replaced.`)) return;
    setStatus(null);
    setBusy(`v${versionNo}`);
    try {
      const restored = await restoreVersion(activeProjectId, versionNo);
      onRestoreScene(restored.sceneGraph as unknown as SceneGraph);
      setOpen(false);
      setStatus(`Restored version ${versionNo}`);
    } catch (e) {
      setStatus(e instanceof Error ? e.message : 'Restore failed');
    } finally {
      setBusy(null);
    }
  }

  const btn =
    'flex h-7 items-center justify-center gap-1 rounded-[8px] px-2 text-[12px] font-medium text-secondary transition-colors hover:bg-raised disabled:opacity-40';

  return (
    <div className="relative flex items-center gap-1">
      {shared ? (
        <span
          className={`rounded-[8px] px-2 py-1 text-[11px] font-medium ${
            isViewOnly ? 'bg-raised text-muted' : 'bg-accent/10 text-accent'
          }`}
          title={isViewOnly ? 'This design is shared as view-only' : 'This design is shared for editing'}
        >
          {isViewOnly ? 'View only' : 'Shared · edit'}
        </span>
      ) : (
        activeProjectId && (
          <span className="hidden max-w-[140px] truncate text-[11px] text-muted xl:inline" title={projectName}>
            {projectName}
          </span>
        )
      )}
      {!isViewOnly && (
        <button
          type="button"
          className={btn}
          onClick={() => void handleSaveProject()}
          disabled={busy !== null}
          title={shared ? 'Save changes to the shared design' : 'Save to your projects (sign in required)'}
          data-testid="save-project-btn"
        >
          {busy === 'save' ? 'Saving…' : shared ? 'Save changes' : activeProjectId ? 'Update project' : 'Save to projects'}
        </button>
      )}
      {!shared && (
        <button
          type="button"
          className={btn}
          onClick={() => setOpen((v) => !v)}
          disabled={!activeProjectId || busy !== null}
          title={activeProjectId ? 'Versions & restore' : 'Save the project first'}
          data-testid="versions-btn"
        >
          Versions {versions.length > 0 ? `(${versions.length})` : ''}
        </button>
      )}
      {status && (
        <span className="ml-1 text-[12px] text-secondary" role="status">
          {status}
        </span>
      )}
      {open && activeProjectId && (
        <div
          className="absolute right-0 top-8 z-20 min-w-[240px] rounded-[12px] border border-bordered bg-surface p-2 shadow-xl"
          data-testid="versions-menu"
        >
          <button
            type="button"
            className="flex h-8 w-full items-center rounded-[8px] px-2 text-left text-[12px] font-medium text-accent transition-colors hover:bg-raised"
            onClick={() => void handleSaveVersion()}
            disabled={busy === 'version'}
          >
            {busy === 'version' ? 'Saving…' : 'Save current as version'}
          </button>
          <div className="my-1 h-px bg-bordered" />
          {versions.length === 0 ? (
            <p className="px-2 py-1 text-[12px] text-muted">No versions yet</p>
          ) : (
            [...versions].reverse().map((v) => (
              <button
                key={v.id}
                type="button"
                className="flex h-8 w-full items-center justify-between rounded-[8px] px-2 text-left text-[12px] transition-colors hover:bg-raised"
                onClick={() => void handleRestore(v.versionNo)}
              >
                <span>{v.label ?? `Version ${v.versionNo}`}</span>
                <span className="text-muted">v{v.versionNo}</span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

// -- sharing ----------------------------------------------------------------

function ShareControl({
  activeProjectId,
  onProjectChange,
  readScene,
}: {
  activeProjectId: string | null;
  onProjectChange: (id: string, name: string) => void;
  readScene: () => Record<string, unknown>;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [shares, setShares] = useState<Share[]>([]);
  const [permission, setPermission] = useState<'view' | 'edit'>('view');
  const [busy, setBusy] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const refresh = useCallback(async () => {
    if (!activeProjectId) return;
    try {
      setShares(await listShares(activeProjectId));
    } catch {
      // non-fatal
    }
  }, [activeProjectId]);

  useEffect(() => {
    if (open && activeProjectId) void refresh();
  }, [open, activeProjectId, refresh]);

  async function ensureProjectSaved(): Promise<string | null> {
    if (activeProjectId) return activeProjectId;
    const { createProject, getToken } = await import('@/lib/api');
    if (!getToken()) {
      router.push(`/login?redirect=${encodeURIComponent(window.location.href)}`);
      return null;
    }
    const name = window.prompt('Name this project before sharing', 'Untitled design');
    if (!name?.trim()) return null;
    const created = await createProject(name.trim(), readScene());
    onProjectChange(created.id, created.name);
    router.replace(`/editor?project=${created.id}`, { scroll: false });
    return created.id;
  }

  async function handleCreate() {
    setStatus(null);
    setBusy('create');
    try {
      const projectId = await ensureProjectSaved();
      if (!projectId) return;
      const share = await createShare(projectId, permission);
      setShares(await listShares(projectId));
      const link = shareUrl(share.token);
      try {
        await navigator.clipboard?.writeText(link);
      } catch {
        // clipboard may be blocked; the link is still shown in the list
      }
      setCopied(true);
      setStatus('Share link copied to clipboard');
      setTimeout(() => setCopied(false), 1500);
    } catch (e) {
      setStatus(e instanceof Error ? e.message : 'Share failed');
    } finally {
      setBusy(null);
    }
  }

  async function handleRevoke(token: string) {
    if (!activeProjectId) return;
    setStatus(null);
    setBusy(token);
    try {
      await revokeShare(activeProjectId, token);
      await refresh();
      setStatus('Share link revoked');
    } catch (e) {
      setStatus(e instanceof Error ? e.message : 'Revoke failed');
    } finally {
      setBusy(null);
    }
  }

  const btn =
    'flex h-7 items-center justify-center gap-1 rounded-[8px] px-2 text-[12px] font-medium text-secondary transition-colors hover:bg-raised disabled:opacity-40';

  return (
    <div className="relative flex items-center">
      <button
        type="button"
        className={btn}
        onClick={() => setOpen((v) => !v)}
        title="Share this design with a link"
        data-testid="share-btn"
      >
        Share
      </button>
      {open && (
        <div
          className="absolute right-0 top-8 z-20 w-[300px] rounded-[12px] border border-bordered bg-surface p-3 shadow-xl"
          data-testid="share-menu"
        >
          <p className="text-[13px] font-semibold">Share design</p>
          <p className="mt-0.5 text-[12px] text-secondary">
            Anyone with the link can {permission === 'edit' ? 'edit' : 'view'} this design.
          </p>

          <div className="mt-3 flex items-center gap-2">
            <button
              type="button"
              className={`h-8 flex-1 rounded-[8px] text-[12px] font-medium transition-colors ${
                permission === 'view' ? 'bg-raised text-primary' : 'text-secondary hover:bg-raised'
              }`}
              onClick={() => setPermission('view')}
            >
              View only
            </button>
            <button
              type="button"
              className={`h-8 flex-1 rounded-[8px] text-[12px] font-medium transition-colors ${
                permission === 'edit' ? 'bg-raised text-primary' : 'text-secondary hover:bg-raised'
              }`}
              onClick={() => setPermission('edit')}
            >
              Can edit
            </button>
          </div>

          <button
            type="button"
            className="mt-3 h-9 w-full rounded-[10px] bg-accent text-[13px] font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-40"
            onClick={() => void handleCreate()}
            disabled={busy === 'create'}
            data-testid="create-share-btn"
          >
            {busy === 'create' ? 'Creating…' : copied ? 'Link copied!' : 'Create share link'}
          </button>

          {shares.length > 0 && (
            <ul className="mt-3 flex flex-col gap-1">
              {shares.map((s) => (
                <li
                  key={s.token}
                  className="flex items-center justify-between gap-2 rounded-[8px] bg-raised px-2 py-1.5"
                >
                  <span className="truncate text-[12px] text-secondary">
                    {s.permission === 'edit' ? 'Edit' : 'View'} · {s.token.slice(0, 8)}…
                  </span>
                  <button
                    type="button"
                    className="text-[11px] font-medium text-danger hover:underline"
                    onClick={() => void handleRevoke(s.token)}
                    disabled={busy === s.token}
                  >
                    {busy === s.token ? '…' : 'Revoke'}
                  </button>
                </li>
              ))}
            </ul>
          )}

          {status && (
            <p className="mt-2 text-[12px] text-secondary" role="status">
              {status}
            </p>
          )}
        </div>
      )}
    </div>
  );
}