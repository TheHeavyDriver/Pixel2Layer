export interface UploadResponse {
  uploadId: string;
  key: string;
  url: string;
  contentType: string;
  extension: string;
  sizeBytes: number;
  sha256: string;
}

export interface JobResponse {
  id: string;
  uploadId: string;
  status: 'queued' | 'running' | 'done' | 'failed';
  stage: string;
  stageProgress: number;
  progress: number;
  error?: string | null;
  result?: Record<string, unknown> | null;
}

export const STAGES = [
  'uploading',
  'analyzing',
  'text',
  'shapes',
  'colors',
  'segmenting',
  'vectorizing',
  'building',
  'exporting',
] as const;

export type Stage = (typeof STAGES)[number];

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

export async function uploadImage(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE}/api/upload`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Upload failed (${res.status})`);
  }
  return res.json();
}

export async function createJob(uploadId: string): Promise<JobResponse> {
  const res = await fetch(`${API_BASE}/api/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ upload_id: uploadId }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Job creation failed (${res.status})`);
  }
  return res.json();
}

export async function getJob(jobId: string): Promise<JobResponse> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}`);
  if (!res.ok) {
    throw new Error(`Job lookup failed (${res.status})`);
  }
  return res.json();
}

/**
 * Subscribe to job progress via Server-Sent Events. Calls `onUpdate` for
 * every snapshot and resolves when the job reaches a terminal state.
 */
export async function subscribeToJob(
  jobId: string,
  onUpdate: (job: JobResponse) => void,
  signal?: AbortSignal,
): Promise<JobResponse> {
  return new Promise((resolve, reject) => {
    const source = new EventSource(`${API_BASE}/api/jobs/${jobId}/events`);
    let terminal: JobResponse | null = null;
    let done = false;

    const finish = (err?: unknown) => {
      if (done) return;
      done = true;
      source.close();
      if (err) reject(err);
      else resolve(terminal ?? ({ id: jobId, status: 'done' } as JobResponse));
    };

    source.addEventListener('update', (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data) as JobResponse;
        onUpdate(data);
        if (data.status === 'done' || data.status === 'failed') terminal = data;
      } catch {
        // ignore malformed frames
      }
    });

    source.addEventListener('done', () => finish());

    source.onerror = () => {
      finish(new Error('Connection to the reconstruction stream was lost.'));
    };

    signal?.addEventListener('abort', () => finish());
  });
}