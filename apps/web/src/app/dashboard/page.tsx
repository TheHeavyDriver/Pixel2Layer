'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

import {
  deleteProject,
  getCurrentUser,
  listProjects,
  logout,
  updateProject,
  type AuthUser,
  type ProjectSummary,
} from '@/lib/api';

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');

  useEffect(() => {
    let cancelled = false;
    async function init() {
      const me = await getCurrentUser();
      if (cancelled) return;
      if (!me) {
        router.replace(`/login?redirect=/dashboard`);
        return;
      }
      setUser(me);
      try {
        setProjects(await listProjects());
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load projects.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void init();
    return () => {
      cancelled = true;
    };
  }, [router]);

  const handleDelete = useCallback(
    async (id: string) => {
      if (!window.confirm('Delete this project? This cannot be undone.')) return;
      try {
        await deleteProject(id);
        setProjects((prev) => prev.filter((p) => p.id !== id));
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Delete failed.');
      }
    },
    [],
  );

  const startRename = useCallback((id: string, name: string) => {
    setRenamingId(id);
    setRenameValue(name);
  }, []);

  const commitRename = useCallback(
    async (id: string) => {
      const name = renameValue.trim();
      if (!name) {
        setRenamingId(null);
        return;
      }
      try {
        await updateProject(id, { name });
        setProjects((prev) => prev.map((p) => (p.id === id ? { ...p, name } : p)));
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Rename failed.');
      } finally {
        setRenamingId(null);
      }
    },
    [renameValue],
  );

  const openProject = useCallback(
    (id: string) => router.push(`/editor?project=${id}`),
    [router],
  );

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-base">
        <div className="flex items-center gap-3 text-[13px] text-secondary">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          Loading…
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-base px-6 py-6">
      <nav className="mx-auto flex w-full max-w-4xl items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="h-5 w-5 rounded-[4px] bg-accent" aria-hidden />
          <span className="text-[15px] font-semibold tracking-[-0.02em]">Pixel2Layer</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => router.push('/')}
            className="h-9 rounded-[10px] border border-bordered px-4 text-[13px] font-medium text-secondary transition-colors hover:bg-raised"
          >
            New from image
          </button>
          {user && (
            <>
              <span className="hidden text-[13px] text-secondary sm:inline">{user.email}</span>
              <button
                type="button"
                onClick={() => {
                  logout();
                  router.push('/');
                }}
                className="h-9 rounded-[10px] px-3 text-[13px] font-medium text-secondary transition-colors hover:bg-raised"
                data-testid="logout-btn"
              >
                Log out
              </button>
            </>
          )}
        </div>
      </nav>

      <div className="mx-auto mt-10 max-w-4xl">
        <h1 className="text-[28px] font-semibold tracking-[-0.02em]">Your projects</h1>
        <p className="mt-1 text-[14px] text-secondary">
          Reopen a design and keep editing it from any browser.
        </p>

        {error && <p className="mt-4 text-[13px] text-danger" role="alert">{error}</p>}

        {projects.length === 0 ? (
          <div className="mt-10 rounded-[16px] border border-dashed border-bordered-strong bg-surface/50 p-10 text-center">
            <p className="text-[15px] font-medium">No projects yet</p>
            <p className="mt-1 text-[13px] text-secondary">
              Upload an image, reconstruct it, then save it here to keep it forever.
            </p>
            <button
              type="button"
              onClick={() => router.push('/')}
              className="mt-6 h-10 rounded-[10px] bg-accent px-5 text-[13px] font-medium text-white transition-colors hover:bg-accent-hover"
            >
              Start a project from an image
            </button>
          </div>
        ) : (
          <ul className="mt-8 flex flex-col gap-2" data-testid="project-list">
            {projects.map((p) => (
              <li
                key={p.id}
                className="flex items-center gap-3 rounded-[12px] border border-bordered bg-surface px-4 py-3 transition-colors hover:border-bordered-strong"
                data-testid="project-row"
              >
                <button
                  type="button"
                  onClick={() => openProject(p.id)}
                  className="flex-1 text-left"
                >
                  {renamingId === p.id ? (
                    <input
                      autoFocus
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      onBlur={() => void commitRename(p.id)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') void commitRename(p.id);
                        if (e.key === 'Escape') setRenamingId(null);
                      }}
                      className="h-7 w-full max-w-xs rounded-[8px] border border-bordered px-2 text-[13px] outline-none focus:border-accent"
                    />
                  ) : (
                    <span className="text-[14px] font-medium hover:text-accent">{p.name}</span>
                  )}
                  <span className="mt-0.5 block text-[12px] text-muted">
                    Edited {formatDate(p.updatedAt)}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => startRename(p.id, p.name)}
                  className="h-8 rounded-[8px] px-3 text-[12px] font-medium text-secondary transition-colors hover:bg-raised"
                >
                  Rename
                </button>
                <button
                  type="button"
                  onClick={() => void handleDelete(p.id)}
                  className="h-8 rounded-[8px] px-3 text-[12px] font-medium text-danger transition-colors hover:bg-raised"
                >
                  Delete
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </main>
  );
}