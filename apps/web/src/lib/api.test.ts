import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  API_BASE,
  createJob,
  exportScene,
  getJob,
  importProjectP2l,
  uploadImage,
} from '@/lib/api';

describe('api client', () => {
  const fetchMock = vi.fn();
  globalThis.fetch = fetchMock as unknown as typeof fetch;

  afterEach(() => {
    fetchMock.mockReset();
  });

  it('uploadImage posts multipart form data and returns the upload payload', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ uploadId: 'u1', key: 'abc' }, 200));

    const out = await uploadImage(new File(['x'], 'a.png', { type: 'image/png' }));

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/upload`);
    expect(init.method).toBe('POST');
    expect(init.body).toBeInstanceOf(FormData);
    expect(out.uploadId).toBe('u1');
  });

  it('createJob posts the upload id as JSON', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ id: 'j1', uploadId: 'u1', status: 'queued' }, 200));

    const out = await createJob('u1');

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe('POST');
    expect(init.headers).toEqual({ 'Content-Type': 'application/json' });
    expect(JSON.parse(String(init.body))).toEqual({ upload_id: 'u1' });
    expect(out.id).toBe('j1');
  });

  it('getJob fetches a single job', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ id: 'j1', status: 'running' }, 200));

    const out = await getJob('j1');

    expect(fetchMock.mock.calls[0][0]).toBe(`${API_BASE}/api/jobs/j1`);
    expect(out.status).toBe('running');
  });

  it('exportScene posts the scene graph and returns a blob', async () => {
    const blob = new Blob(['png-bytes'], { type: 'image/png' });
    const response = { ok: true, blob: () => Promise.resolve(blob) } as unknown as Response;
    fetchMock.mockResolvedValueOnce(response);

    const out = await exportScene({ format: 'png', canvas: { width: 300, height: 200, background: '#fff' }, layers: [] });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(String(init.body));
    expect(body.format).toBe('png');
    expect(body.scene.canvas.width).toBe(300);
    expect(init.method).toBe('POST');
    expect(out).toBe(blob);
  });

  it('importProjectP2l posts a multipart file', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ schemaVersion: 1, layers: [] }, 200));

    const out = await importProjectP2l(new Blob(['{}'], { type: 'application/json' }));

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((init.body as FormData).get('file')).toBeInstanceOf(Blob);
    expect(out).toEqual({ schemaVersion: 1, layers: [] });
  });

  it('getJob propagates non-2xx as a descriptive error', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: 'Not found' }, 404));

    await expect(getJob('missing')).rejects.toThrow('Job lookup failed (404)');
  });
});

function jsonResponse(payload: unknown, status: number): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(payload),
  } as unknown as Response;
}