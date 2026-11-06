'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

import type { SceneGraph } from '@pixel2layer/schema';

import {
  createProject,
  getToken,
  listVersions,
  restoreVersion,
  saveVersion,
  updateProject,
  type Version,
} from '@/lib/api';
import { extractErrorMessage } from '@/lib/error-utils';

interface CloudSaveControlProps {
  activeProjectId: string | null;
  projectName: string;
  shared: { token: string; permission: 'view' | 'edit' } | null;
  onProjectChange: (id: string, name: string) => void;
  onRestoreScene: (scene: SceneGraph) => void;
  readScene: () => Record<string, unknown>;
}

export function CloudSaveControl({
  activeProjectId,
  projectName,
  shared,
  onProjectChange,
  onRestoreScene,
  readScene,
}: CloudSaveControlProps) {
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
      setStatus(extractErrorMessage(e, 'Save failed'));
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
      setStatus(extractErrorMessage(e, 'Save failed'));
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
      setStatus(extractErrorMessage(e, 'Restore failed'));
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
