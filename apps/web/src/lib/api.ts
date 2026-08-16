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

const JSON_HEADERS = { 'Content-Type': 'application/json' };

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Request failed (${res.status})`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

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
    headers: JSON_HEADERS,
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

export interface ExportOptions {
  format: 'png' | 'jpg' | 'svg' | 'pdf';
  /** canvas width, height, background from the scene graph */
  canvas: { width: number; height: number; background: string | null };
  /** ordered back-to-front geometry in SceneGraphSchema form */
  layers: unknown[];
  confidence?: Record<string, number>;
  overallConfidence?: number;
}

export interface ExportResponse {
  url: string;
  contentType: string;
  filename: string;
}

/** Ask the API to rasterize/serialize a scene graph. Returns a Blob of file bytes. */
export async function exportScene(
  scene: ExportOptions,
  { download = true }: { download?: boolean } = {},
): Promise<Blob> {
  const body = {
    format: scene.format,
    scan: 1,
    scene: {
      schemaVersion: 1,
      canvas: scene.canvas,
      layers: scene.layers,
      confidence: scene.confidence ?? {},
      overallConfidence: scene.overallConfidence ?? 0.8,
    },
  };
  const res = await fetch(`${API_BASE}/api/export`, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Export failed (${res.status})`);
  }
  void download;
  return res.blob();
}

/** Download a .p2l project file for a scene graph. */
export async function saveProjectP2l(
  scene: Omit<ExportOptions, 'format'>,
  name: string,
): Promise<Blob> {
  const body = {
    scene: {
      schemaVersion: 1,
      canvas: scene.canvas,
      layers: scene.layers,
      confidence: scene.confidence ?? {},
      overallConfidence: scene.overallConfidence ?? 0.8,
    },
    name,
  };
  const res = await fetch(`${API_BASE}/api/export/p2l`, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Save failed (${res.status})`);
  }
  return res.blob();
}

/** Read an uploaded .p2l file and return its scene graph. */
export async function importProjectP2l(file: Blob): Promise<Record<string, unknown>> {
  const form = new FormData();
  form.append('file', file, 'design.p2l');
  const res = await fetch(`${API_BASE}/api/export/import`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Import failed (${res.status})`);
  }
  return res.json();
}

// -- auth -------------------------------------------------------------------

export interface AuthUser {
  id: string;
  email: string;
  name: string | null;
}

export interface AuthResponse {
  token: string;
  user: AuthUser;
}

const TOKEN_KEY = 'pixel2layer.token';

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (typeof window === 'undefined') return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

/** fetch that attaches the stored bearer token to authenticated endpoints. */
async function authFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const headers = new Headers(init?.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (init?.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  return handle<T>(await fetch(`${API_BASE}${path}`, { ...init, headers }));
}

async function authRequest(path: string, method: string, body: unknown): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `${path} failed (${res.status})`);
  }
  const parsed = (await res.json()) as AuthResponse;
  setToken(parsed.token);
  return parsed;
}

export async function register(input: {
  email: string;
  password: string;
  name?: string;
}): Promise<AuthResponse> {
  return authRequest('/api/auth/register', 'POST', input);
}

export async function login(input: { email: string; password: string }): Promise<AuthResponse> {
  return authRequest('/api/auth/login', 'POST', input);
}

export function logout(): void {
  setToken(null);
}

/** Resolve the signed-in user, or null when no token exists / the token is invalid. */
export async function getCurrentUser(): Promise<AuthUser | null> {
  if (!getToken()) return null;
  try {
    return await authFetch<AuthUser>('/api/auth/me');
  } catch {
    setToken(null);
    return null;
  }
}

// -- projects ----------------------------------------------------------------

export interface ProjectSummary {
  id: string;
  name: string;
  sourceImage: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface Project extends ProjectSummary {
  sceneGraph: Record<string, unknown>;
}

export interface Version {
  id: string;
  projectId: string;
  versionNo: number;
  label: string | null;
  sceneGraph: Record<string, unknown>;
  createdAt: string;
}

export async function createProject(
  name: string,
  sceneGraph: Record<string, unknown>,
  sourceImage?: string,
): Promise<Project> {
  return authFetch<Project>('/api/projects', {
    method: 'POST',
    body: JSON.stringify({ name, sceneGraph, sourceImage }),
  });
}

export async function listProjects(): Promise<ProjectSummary[]> {
  return authFetch<ProjectSummary[]>('/api/projects');
}

export async function getProject(projectId: string): Promise<Project> {
  return authFetch<Project>(`/api/projects/${projectId}`);
}

export async function updateProject(
  projectId: string,
  patch: { name?: string; sceneGraph?: Record<string, unknown> },
): Promise<Project> {
  return authFetch<Project>(`/api/projects/${projectId}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  });
}

export async function deleteProject(projectId: string): Promise<void> {
  return authFetch<void>(`/api/projects/${projectId}`, { method: 'DELETE' });
}

export async function saveVersion(
  projectId: string,
  sceneGraph: Record<string, unknown>,
  label?: string,
): Promise<Version> {
  return authFetch<Version>(`/api/projects/${projectId}/versions`, {
    method: 'POST',
    body: JSON.stringify({ sceneGraph, label }),
  });
}

export async function listVersions(projectId: string): Promise<Version[]> {
  return authFetch<Version[]>(`/api/projects/${projectId}/versions`);
}

export async function restoreVersion(
  projectId: string,
  versionNo: number,
): Promise<Project> {
  return authFetch<Project>(`/api/projects/${projectId}/versions/${versionNo}/restore`, {
    method: 'POST',
  });
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
        // the terminal snapshot's `update` event is the authoritative signal;
        // the trailing `done` event can be dropped by the transport (e.g. an
        // incomplete-chunk close in Chromium), so resolve here when possible.
        if (data.status === 'done' || data.status === 'failed') {
          terminal = data;
          finish();
        }
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

// -- sharing ----------------------------------------------------------------

export interface Share {
  token: string;
  projectId: string;
  permission: 'view' | 'edit';
  url: string;
  createdAt: string;
}

export interface SharedProject {
  id: string;
  name: string;
  sceneGraph: Record<string, unknown>;
  sourceImage: string | null;
  permission: 'view' | 'edit';
  updatedAt: string;
}

export async function createShare(
  projectId: string,
  permission: 'view' | 'edit',
): Promise<Share> {
  return authFetch<Share>(`/api/projects/${projectId}/share`, {
    method: 'POST',
    body: JSON.stringify({ permission }),
  });
}

export async function listShares(projectId: string): Promise<Share[]> {
  return authFetch<Share[]>(`/api/projects/${projectId}/shares`);
}

export async function revokeShare(projectId: string, token: string): Promise<void> {
  return authFetch<void>(`/api/projects/${projectId}/shares/${token}`, {
    method: 'DELETE',
  });
}

export function shareUrl(token: string): string {
  return `${window.location.origin}/share/${token}`;
}

export async function getSharedProject(token: string): Promise<SharedProject> {
  return handle<SharedProject>(await fetch(`${API_BASE}/api/share/${token}`));
}

export async function updateSharedProject(
  token: string,
  sceneGraph: Record<string, unknown>,
): Promise<SharedProject> {
  const res = await fetch(`${API_BASE}/api/share/${token}`, {
    method: 'PATCH',
    headers: JSON_HEADERS,
    body: JSON.stringify({ sceneGraph }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Share update failed (${res.status})`);
  }
  return res.json();
}

// -- templates --------------------------------------------------------------

export interface TemplateSummary {
  id: string;
  ownerId: string;
  name: string;
  sourceImage: string | null;
  createdAt: string;
}

export interface Template extends TemplateSummary {
  sceneGraph: Record<string, unknown>;
}

export async function createTemplate(
  name: string,
  sceneGraph: Record<string, unknown>,
  sourceImage?: string,
): Promise<Template> {
  return authFetch<Template>('/api/templates', {
    method: 'POST',
    body: JSON.stringify({ name, sceneGraph, sourceImage }),
  });
}

export async function listTemplates(): Promise<TemplateSummary[]> {
  return handle<TemplateSummary[]>(await fetch(`${API_BASE}/api/templates`));
}

export async function getTemplate(templateId: string): Promise<Template> {
  return handle<Template>(await fetch(`${API_BASE}/api/templates/${templateId}`));
}

export async function deleteTemplate(templateId: string): Promise<void> {
  return authFetch<void>(`/api/templates/${templateId}`, { method: 'DELETE' });
}

// -- batches ----------------------------------------------------------------

export interface BatchJob {
  id: string;
  uploadId: string;
  status: 'queued' | 'running' | 'done' | 'failed';
  stage: string;
  progress: number;
}

export interface Batch {
  id: string;
  jobs: BatchJob[];
}

export async function createBatch(uploadIds: string[]): Promise<Batch> {
  return authFetch<Batch>('/api/batches', {
    method: 'POST',
    body: JSON.stringify({ uploadIds }),
  });
}

export async function getBatch(batchId: string): Promise<Batch> {
  return authFetch<Batch>(`/api/batches/${batchId}`);
}

// -- tools (v0.6 backlog) ---------------------------------------------------

export interface BackgroundRemovalResult {
  url: string;
  key: string;
  width: number;
  height: number;
}

export interface GroupSuggestion {
  name: string;
  elementIds: string[];
}

/** Remove the background of an image; returns a stored masked cutout. */
export async function removeBackground(file: Blob): Promise<BackgroundRemovalResult> {
  const form = new FormData();
  form.append('file', file, 'image.png');
  const res = await fetch(`${API_BASE}/api/tools/background-removal`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Background removal failed (${res.status})`);
  }
  return res.json();
}

/** Ask the API for smart layer-grouping suggestions on a scene graph. */
export async function suggestGroups(scene: {
  canvas: { width: number; height: number; background: string | null };
  layers: unknown[];
}): Promise<GroupSuggestion[]> {
  const body = {
    scene: {
      schemaVersion: 1,
      canvas: scene.canvas,
      layers: scene.layers,
      confidence: {},
      overallConfidence: 1,
    },
  };
  const res = await fetch(`${API_BASE}/api/tools/grouping`, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Grouping failed (${res.status})`);
  }
  const parsed = (await res.json()) as { groups: GroupSuggestion[] };
  return parsed.groups;
}

// -- region editing (v0.7 backlog) -------------------------------------------

export interface RegionInfo {
  x: number;
  y: number;
  width: number;
  height: number;
  label: string;
  confidence: number;
}

export interface RegionsResult {
  width: number;
  height: number;
  regions: RegionInfo[];
}

export type RegionMaskMode = 'keep' | 'remove';

/** Detect foreground regions of an image so the editor can offer region
 *  keep/remove/crop actions. */
export async function detectRegions(file: Blob): Promise<RegionsResult> {
  const form = new FormData();
  form.append('file', file, 'image.png');
  const res = await fetch(`${API_BASE}/api/tools/regions`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Region detection failed (${res.status})`);
  }
  return res.json();
}

async function regionEdit(
  endpoint: 'region-crop' | 'region-mask',
  file: Blob,
  index: number,
  mode?: RegionMaskMode,
): Promise<BackgroundRemovalResult> {
  const url = `${API_BASE}/api/tools/${endpoint}?index=${encodeURIComponent(index)}${mode ? `&mode=${encodeURIComponent(mode)}` : ''}`;
  const form = new FormData();
  form.append('file', file, 'image.png');
  const res = await fetch(url, { method: 'POST', body: form });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `${endpoint} failed (${res.status})`);
  }
  return res.json();
}

/** Crop an image to a single detected region's bounding box. */
export async function cropRegion(file: Blob, index: number): Promise<BackgroundRemovalResult> {
  return regionEdit('region-crop', file, index);
}

/** Mask an image with a single detected region (keep or remove its pixels). */
export async function maskRegion(
  file: Blob,
  index: number,
  mode: RegionMaskMode,
): Promise<BackgroundRemovalResult> {
  return regionEdit('region-mask', file, index, mode);
}