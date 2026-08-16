'use client';

import { useEffect, useMemo, useState } from 'react';

import { STAGES, type JobResponse, type Stage } from '@/lib/api';

interface ProgressScreenProps {
  jobId: string;
  onDone: (job: JobResponse) => void;
  onCancel: () => void;
}

const STAGE_LABELS: Record<(typeof STAGES)[number], string> = {
  uploading: 'Uploading',
  analyzing: 'Analyzing image',
  text: 'Detecting text',
  shapes: 'Finding shapes',
  colors: 'Extracting colors',
  segmenting: 'Segmenting photos',
  vectorizing: 'Vectorizing graphics',
  building: 'Building layers',
  exporting: 'Exporting',
};

type StageState = 'pending' | 'running' | 'done' | 'failed';

export function ProgressScreen({ jobId, onDone, onCancel }: ProgressScreenProps) {
  const [job, setJob] = useState<JobResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let stream: Promise<JobResponse>;

    // import api lazily to avoid evaluating on the server
    import('@/lib/api').then(async ({ subscribeToJob }) => {
      try {
        stream = subscribeToJob(jobId, (j) => {
          if (!cancelled) setJob(j);
        });
        const final = await stream;
        if (!cancelled) onDone(final.status === 'done' ? (job ?? final) : final);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Reconstruction failed.');
      }
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  const stageStates = useMemo(() => {
    if (!job) return {} as Record<Stage, StageState>;
    const idx = STAGES.indexOf(job.stage as Stage);
    const out = {} as Record<Stage, StageState>;
    STAGES.forEach((s, i) => {
      if (job.status === 'failed' && s === job.stage) out[s] = 'failed';
      else if (i < idx || job.status === 'done') out[s] = 'done';
      else if (i === idx) out[s] = 'running';
      else out[s] = 'pending';
    });
    return out;
  }, [job]);

  const activeIdx = job ? STAGES.indexOf(job.stage as Stage) : 1;
  void activeIdx;

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-base px-4">
      <div className="w-full max-w-[480px]">
        <h1 className="text-center text-[24px] font-semibold tracking-[-0.02em]">
          Reconstructing your design
        </h1>
        <p className="mt-1 text-center text-[13px] text-secondary">
          Simple posters take ~5s. Complex photos can take longer.
        </p>

        <div className="mt-8 rounded-lg border border-bordered bg-surface p-5">
          {STAGES.map((s) => {
            const state = stageStates[s];
            const isCurrent = state === 'running';
            return (
              <div
                key={s}
                className={`flex items-center gap-3 py-2 text-[13px] ${
                  state === 'pending' ? 'text-muted' : 'text-primary'
                }`}
                data-testid={`stage-${s}`}
              >
                {state === 'done' ? (
                  <span className="flex h-5 w-5 items-center justify-center text-success">✓</span>
                ) : state === 'failed' ? (
                  <span className="flex h-5 w-5 items-center justify-center text-danger">✕</span>
                ) : isCurrent ? (
                  <span className="h-5 w-5 animate-pulse rounded-full border-2 border-accent" />
                ) : (
                  <span className="h-5 w-5 rounded-full border-2 border-bordered" />
                )}
                <span className="flex-1">{STAGE_LABELS[s]}</span>
                {state === 'running' && isCurrent && (
                  <span className="font-mono text-[12px] text-accent">
                    {Math.round((job?.stageProgress ?? 0) * 100)}%
                  </span>
                )}
                {state === 'done' && <span className="text-[12px] text-muted">100%</span>}
              </div>
            );
          })}

          <div className="mt-4">
            <div className="h-2 w-full overflow-hidden rounded-full bg-raised">
              <div
                className="h-full rounded-full bg-accent transition-all duration-300"
                style={{ width: `${Math.round((job?.progress ?? 0) * 100)}%` }}
                data-testid="overall-progress"
              />
            </div>
            <div className="mt-1 text-right font-mono text-[12px] text-secondary">
              {Math.round((job?.progress ?? 0) * 100)}%
            </div>
          </div>

          {error && (
            <div className="mt-4 rounded-lg border border-danger/30 bg-danger/10 p-3 text-[13px] text-danger">
              {error}
            </div>
          )}
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