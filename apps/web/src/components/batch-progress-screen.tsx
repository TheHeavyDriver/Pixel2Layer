'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';

import { type BatchJob, type JobResponse, subscribeToJob } from '@/lib/api';

interface BatchProgressScreenProps {
  batchId: string;
  initialJobs: BatchJob[];
  onCancel: () => void;
}

type RowState = Record<string, JobResponse>;

export function BatchProgressScreen({
  batchId,
  initialJobs,
  onCancel,
}: BatchProgressScreenProps) {
  const router = useRouter();
  const [jobs, setJobs] = useState<BatchJob[]>(initialJobs);
  const [rows, setRows] = useState<RowState>({});
  const [done, setDone] = useState(0);
  const [failed, setFailed] = useState(0);
  const rowRef = useRef<RowState>({});

  const updateRow = useCallback((jobId: string, job: JobResponse) => {
    rowRef.current = { ...rowRef.current, [jobId]: job };
    setRows(rowRef.current);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const controllers: AbortController[] = [];

    const count = () => {
      if (!cancelled) {
        setDone(Object.values(rowRef.current).filter((r) => r.status === 'done').length);
        setFailed(Object.values(rowRef.current).filter((r) => r.status === 'failed').length);
      }
    };

    initialJobs.forEach((j) => {
      const controller = new AbortController();
      controllers.push(controller);
      import('@/lib/api').then(({ subscribeToJob }) =>
        subscribeToJob(j.id, (snap) => {
          updateRow(j.id, snap);
          if (snap.status === 'done' || snap.status === 'failed') count();
        }).catch(() => {
          updateRow(j.id, { id: j.id, uploadId: j.uploadId, status: 'failed', stage: 'failed', stageProgress: 0, progress: 0, error: 'failed' });
          count();
        }),
      );
    });

    return () => {
      cancelled = true;
      controllers.forEach((c) => c.abort());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const total = jobs.length;
  const completed = done + failed;
  const overallPct = total > 0 ? Math.round((completed / total) * 100) : 0;

  const openResult = useCallback(
    (j: BatchJob) => {
      const row = rows[j.id];
      if (row?.status === 'done' || row?.status === 'failed') {
        router.push(`/editor?job=${j.id}`);
      }
    },
    [rows, router],
  );

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-base px-4">
      <div className="w-full max-w-[520px]">
        <h1 className="text-center text-[24px] font-semibold tracking-[-0.02em]">
          Reconstructing {total} {total === 1 ? 'design' : 'designs'}
        </h1>
        <p className="mt-1 text-center text-[13px] text-secondary">
          Each image reconstructs independently.
        </p>

        <div className="mt-8 rounded-lg border border-bordered bg-surface p-5">
          <ul className="flex flex-col gap-2" data-testid="batch-list">
            {jobs.map((j) => {
              const row = rows[j.id];
              const status = row?.status ?? j.status;
              const pct = row?.progress ?? j.progress;
              return (
                <li
                  key={j.id}
                  className="rounded-[10px] bg-raised px-3 py-2"
                  data-testid="batch-row"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={`h-5 w-5 shrink-0 rounded-full border-2 ${
                        status === 'done'
                          ? 'border-success text-success'
                          : status === 'failed'
                            ? 'border-danger text-danger'
                            : 'animate-pulse border-accent'
                      }`}
                    >
                      {status === 'done' && <span className="flex h-full items-center justify-center text-[11px]">✓</span>}
                      {status === 'failed' && <span className="flex h-full items-center justify-center text-[11px]">✕</span>}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between">
                        <span className="truncate text-[12px] font-medium">
                          {j.uploadId.slice(0, 8)}…
                        </span>
                        <span className="font-mono text-[11px] text-secondary">
                          {Math.round(pct * 100)}%
                        </span>
                      </div>
                      <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-bordered">
                        <div
                          className="h-full rounded-full bg-accent transition-all duration-300"
                          style={{ width: `${Math.round(pct * 100)}%` }}
                        />
                      </div>
                    </div>
                    {(status === 'done' || status === 'failed') && (
                      <button
                        type="button"
                        onClick={() => openResult(j)}
                        className="h-7 shrink-0 rounded-[8px] bg-accent px-3 text-[12px] font-medium text-white transition-colors hover:bg-accent-hover"
                        data-testid={`open-${j.id}`}
                      >
                        Open
                      </button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>

          <div className="mt-4">
            <div className="h-2 w-full overflow-hidden rounded-full bg-raised">
              <div
                className="h-full rounded-full bg-accent transition-all duration-300"
                style={{ width: `${overallPct}%` }}
              />
            </div>
            <div className="mt-1 text-right font-mono text-[12px] text-secondary">
              {completed}/{total} done
            </div>
          </div>
        </div>

        <div className="mt-4 flex justify-center">
          <button
            type="button"
            onClick={onCancel}
            className="h-9 rounded-[10px] px-4 text-[13px] font-medium text-secondary transition-colors hover:bg-raised"
          >
            Cancel
          </button>
        </div>
      </div>
    </main>
  );
}