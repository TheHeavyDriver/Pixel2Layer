'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

import {
  createProject,
  createShare,
  getToken,
  listShares,
  revokeShare,
  shareUrl,
  type Share,
} from '@/lib/api';
import { extractErrorMessage } from '@/lib/error-utils';

interface ShareControlProps {
  activeProjectId: string | null;
  onProjectChange: (id: string, name: string) => void;
  readScene: () => Record<string, unknown>;
}

export function ShareControl({
  activeProjectId,
  onProjectChange,
  readScene,
}: ShareControlProps) {
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
      setStatus(extractErrorMessage(e, 'Share failed'));
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
      setStatus(extractErrorMessage(e, 'Revoke failed'));
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
