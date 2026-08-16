'use client';

import { useMemo, useState } from 'react';

import type { SceneGraphElement } from '@pixel2layer/schema';

interface LayersPanelProps {
  layers: SceneGraphElement[];
  selectedIds: string[];
  onSelect: (ids: string[]) => void;
  onToggleVisible: (id: string) => void;
  onToggleLocked: (id: string) => void;
  onRename: (id: string, name: string) => void;
  onDuplicate: (id: string) => void;
  onDelete: (id: string) => void;
  onReorder: (id: string, dir: 1 | -1) => void;
}

const TYPE_LABEL: Record<SceneGraphElement['type'], string> = {
  text: 'T',
  rectangle: '▭',
  circle: '○',
  ellipse: '◯',
  line: '╱',
  polygon: '◮',
  vector: '∿',
  image: '▣',
};

function confidenceTone(c: number): string {
  if (c >= 0.8) return 'text-success';
  if (c >= 0.5) return 'text-warning';
  return 'text-danger';
}

export function LayersPanel({
  layers,
  selectedIds,
  onSelect,
  onToggleVisible,
  onToggleLocked,
  onRename,
  onDuplicate,
  onDelete,
  onReorder,
}: LayersPanelProps) {
  const [filter, setFilter] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState('');

  const visibleLayers = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return layers;
    return layers.filter(
      (l) => l.name.toLowerCase().includes(q) || l.type.toLowerCase().includes(q),
    );
  }, [layers, filter]);

  function startRename(el: SceneGraphElement) {
    setEditingId(el.id);
    setDraft(el.name);
  }

  function commitRename() {
    if (editingId && draft.trim()) onRename(editingId, draft.trim());
    setEditingId(null);
  }

  return (
    <aside
      className="flex h-full w-[240px] flex-col border-r border-bordered bg-surface"
      data-testid="layers-panel"
    >
      <div className="flex h-[44px] items-center justify-between border-b border-bordered px-3">
        <h2 className="text-[13px] font-semibold tracking-[-0.01em]">Layers</h2>
        <button
          type="button"
          className="flex h-6 w-6 items-center justify-center rounded-md text-secondary transition-colors hover:bg-raised"
          title="Add layer (coming soon)"
        >
          +
        </button>
      </div>

      <div className="border-b border-bordered p-2">
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter layers…"
          className="h-8 w-full rounded-md border border-bordered bg-raised px-2 text-[12px] text-primary placeholder:text-muted focus:border-bordered-strong focus:outline-none"
          aria-label="Filter layers"
        />
      </div>

      <ul className="flex-1 overflow-y-auto py-1" role="listbox" aria-label="Layers">
        {visibleLayers.length === 0 && (
          <li className="px-3 py-4 text-[12px] text-muted">
            No layers{filter ? ' match the filter' : ' yet'}.
          </li>
        )}
        {visibleLayers.map((el) => {
          const selected = selectedIds.includes(el.id);
          return (
            <li
              key={el.id}
              data-testid={`layer-${el.id}`}
              className={`group flex cursor-default items-center gap-1 px-2 py-[5px] ${
                selected ? 'bg-accent/10' : 'hover:bg-raised'
              }`}
              onClick={() => onSelect([el.id])}
              role="option"
              aria-selected={selected}
            >
              <button
                type="button"
                role="switch"
                aria-checked={el.visible}
                aria-label={`${el.visible ? 'Hide' : 'Show'} ${el.name}`}
                className={`flex h-5 w-5 items-center justify-center rounded ${
                  el.visible ? 'text-secondary hover:text-primary' : 'text-muted hover:text-secondary'
                }`}
                onClick={(e) => {
                  e.stopPropagation();
                  onToggleVisible(el.id);
                }}
              >
                {el.visible ? (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
                    <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                ) : (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
                    <path d="M2 12s3.5-7 10-7 10 7 10 7" />
                    <path d="m22 22-20-20" />
                  </svg>
                )}
              </button>
              <button
                type="button"
                role="switch"
                aria-checked={el.locked}
                aria-label={`${el.locked ? 'Unlock' : 'Lock'} ${el.name}`}
                className={`flex h-5 w-5 items-center justify-center rounded ${
                  el.locked ? 'text-secondary' : 'text-muted hover:text-secondary'
                }`}
                onClick={(e) => {
                  e.stopPropagation();
                  onToggleLocked(el.id);
                }}
              >
                {el.locked ? (
                  <svg width="10" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
                    <rect x="4" y="11" width="16" height="10" rx="2" />
                    <path d="M8 11V7a4 4 0 0 1 8 0v4" />
                  </svg>
                ) : (
                  <svg width="10" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
                    <rect x="4" y="11" width="16" height="10" rx="2" />
                    <path d="M8 11V7a4 4 0 0 1 7.6-1.9" />
                  </svg>
                )}
              </button>
              <span
                className={`flex h-5 w-5 shrink-0 items-center justify-center text-[12px] text-secondary ${
                  el.locked ? 'text-muted' : ''
                }`}
                aria-hidden
              >
                {TYPE_LABEL[el.type]}
              </span>

              {editingId === el.id ? (
                <input
                  autoFocus
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onBlur={commitRename}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') commitRename();
                    if (e.key === 'Escape') setEditingId(null);
                  }}
                  className="min-w-0 flex-1 rounded border border-accent bg-raised px-1 text-[12px] text-primary focus:outline-none"
                  aria-label="Layer name"
                />
              ) : (
                <span
                  className={`min-w-0 flex-1 truncate text-[12px] ${
                    selected ? 'text-primary' : 'text-secondary'
                  } ${el.locked ? 'opacity-60' : ''}`}
                  onDoubleClick={() => startRename(el)}
                  title={el.name}
                >
                  {el.name}
                </span>
              )}

              <span
                className={`hidden shrink-0 font-mono text-[11px] group-hover:inline ${confidenceTone(
                  el.confidence,
                )}`}
                title={`Confidence ${Math.round(el.confidence * 100)}%`}
              >
                {Math.round(el.confidence * 100)}%
              </span>

              <div className="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
                <button
                  type="button"
                  className="flex h-5 w-5 items-center justify-center text-muted hover:text-primary"
                  title="Duplicate"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDuplicate(el.id);
                  }}
                >
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
                    <rect x="9" y="9" width="12" height="12" rx="2" />
                    <path d="M5 15V5a2 2 0 0 1 2-2h10" />
                  </svg>
                </button>
                <button
                  type="button"
                  className="flex h-5 w-5 items-center justify-center text-muted hover:text-danger"
                  title="Delete"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(el.id);
                  }}
                >
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
                    <path d="M3 6h18" />
                    <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
                  </svg>
                </button>
              </div>
            </li>
          );
        })}
      </ul>

      <div className="border-t border-bordered p-1">
        <div className="flex items-center gap-1 px-1 py-1">
          <button
            type="button"
            className="flex h-6 w-6 items-center justify-center rounded text-secondary transition-colors hover:bg-raised disabled:opacity-40"
            title="Move up in order"
            onClick={() => onReorder(selectedIds[0] ?? '', 1)}
            disabled={!selectedIds.length}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
          </button>
          <button
            type="button"
            className="flex h-6 w-6 items-center justify-center rounded text-secondary transition-colors hover:bg-raised disabled:opacity-40"
            title="Move down in order"
            onClick={() => onReorder(selectedIds[0] ?? '', -1)}
            disabled={!selectedIds.length}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
              <path d="M12 5v14M5 12l7 7 7-7" />
            </svg>
          </button>
        </div>
      </div>
    </aside>
  );
}