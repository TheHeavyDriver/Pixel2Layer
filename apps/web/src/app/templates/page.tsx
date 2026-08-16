'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

import {
  createProject,
  deleteTemplate,
  getCurrentUser,
  getToken,
  listTemplates,
  logout,
  type AuthUser,
  type TemplateSummary,
} from '@/lib/api';

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

export default function TemplatesPage() {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function init() {
      const me = await getCurrentUser();
      if (!cancelled) setUser(me);
      try {
        setTemplates(await listTemplates());
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load templates.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void init();
    return () => {
      cancelled = true;
    };
  }, []);

  const useTemplate = useCallback(
    async (t: TemplateSummary) => {
      setBusyId(t.id);
      setError(null);
      try {
        if (getToken()) {
          // signed in: create a project from the template and open it
          const { getTemplate } = await import('@/lib/api');
          const full = await getTemplate(t.id);
          const project = await createProject(`${t.name} copy`, full.sceneGraph);
          router.push(`/editor?project=${project.id}`);
        } else {
          // signed out: open the template anonymously in the editor
          router.push(`/editor?template=${t.id}`);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Could not open template.');
        setBusyId(null);
      }
    },
    [router],
  );

  const removeTemplate = useCallback(
    async (t: TemplateSummary) => {
      if (!window.confirm('Delete this template?')) return;
      try {
        await deleteTemplate(t.id);
        setTemplates((prev) => prev.filter((x) => x.id !== t.id));
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Delete failed.');
      }
    },
    [],
  );

  return (
    <main className="min-h-screen bg-base px-6 py-6">
      <nav className="mx-auto flex w-full max-w-5xl items-center justify-between">
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
          {user ? (
            <>
              <button
                type="button"
                onClick={() => router.push('/dashboard')}
                className="h-9 rounded-[10px] border border-bordered px-4 text-[13px] font-medium text-secondary transition-colors hover:bg-raised"
              >
                My projects
              </button>
              <button
                type="button"
                onClick={() => {
                  logout();
                  setUser(null);
                }}
                className="h-9 rounded-[10px] px-3 text-[13px] font-medium text-secondary transition-colors hover:bg-raised"
              >
                Log out
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={() => router.push('/login?redirect=/templates')}
              className="h-9 rounded-[10px] border border-bordered px-4 text-[13px] font-medium text-secondary transition-colors hover:bg-raised"
            >
              Sign in
            </button>
          )}
        </div>
      </nav>

      <div className="mx-auto mt-10 max-w-5xl">
        <h1 className="text-[28px] font-semibold tracking-[-0.02em]">Template gallery</h1>
        <p className="mt-1 text-[14px] text-secondary">
          Start any design from a proven layout.
        </p>

        {error && <p className="mt-4 text-[13px] text-danger" role="alert">{error}</p>}

        {loading ? (
          <div className="mt-16 flex items-center justify-center gap-3 text-[13px] text-secondary">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
            Loading templates…
          </div>
        ) : templates.length === 0 ? (
          <div className="mt-10 rounded-[16px] border border-dashed border-bordered-strong bg-surface/50 p-10 text-center">
            <p className="text-[15px] font-medium">No templates yet</p>
            <p className="mt-1 text-[13px] text-secondary">
              Save any reconstructed design as a template from the editor.
            </p>
            <button
              type="button"
              onClick={() => router.push('/')}
              className="mt-6 h-10 rounded-[10px] bg-accent px-5 text-[13px] font-medium text-white transition-colors hover:bg-accent-hover"
            >
              Start from an image
            </button>
          </div>
        ) : (
          <ul className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3" data-testid="template-grid">
            {templates.map((t) => (
              <li
                key={t.id}
                className="flex flex-col rounded-[14px] border border-bordered bg-surface p-4 transition-colors hover:border-bordered-strong"
                data-testid="template-card"
              >
                <div
                  className="flex h-28 w-full items-center justify-center rounded-[10px] bg-gradient-to-br from-accent/15 to-raised"
                  aria-hidden
                >
                  <span className="text-[13px] font-medium text-muted">Preview</span>
                </div>
                <div className="mt-3">
                  <p className="truncate text-[14px] font-medium">{t.name}</p>
                  <p className="mt-0.5 text-[12px] text-muted">
                    Added {formatDate(t.createdAt)}
                  </p>
                </div>
                <div className="mt-3 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => void useTemplate(t)}
                    disabled={busyId === t.id}
                    className="h-9 flex-1 rounded-[10px] bg-accent text-[13px] font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
                    data-testid="use-template-btn"
                  >
                    {busyId === t.id ? 'Opening…' : 'Use template'}
                  </button>
                  {user?.id === t.ownerId && (
                    <button
                      type="button"
                      onClick={() => void removeTemplate(t)}
                      className="h-9 rounded-[10px] px-3 text-[12px] font-medium text-danger transition-colors hover:bg-raised"
                    >
                      Delete
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </main>
  );
}