import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  API_BASE,
  createBatch,
  createShare,
  createTemplate,
  deleteTemplate,
  getBatch,
  getSharedProject,
  getTemplate,
  getToken,
  listShares,
  listTemplates,
  revokeShare,
  setToken,
  shareUrl,
  updateSharedProject,
} from '@/lib/api';

describe('sharing/templates/batches api client', () => {
  const fetchMock = vi.fn();
  globalThis.fetch = fetchMock as unknown as typeof fetch;

  const scene = { schemaVersion: 1, layers: [] };

  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    fetchMock.mockReset();
  });

  it('createShare posts permission with bearer auth', async () => {
    setToken('tok');
    fetchMock.mockResolvedValueOnce(jsonResponse({ token: 'abc', url: '/share/abc', permission: 'edit' }, 201));

    const share = await createShare('p1', 'edit');

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/projects/p1/share`);
    expect(JSON.parse(String(init.body))).toEqual({ permission: 'edit' });
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer tok');
    expect(share.token).toBe('abc');
  });

  it('listShares / revokeShare hit project share endpoints', async () => {
    setToken('tok');
    fetchMock.mockResolvedValueOnce(jsonResponse([{ token: 'abc' }], 200));
    await listShares('p1');
    expect(fetchMock.mock.calls[0][0]).toBe(`${API_BASE}/api/projects/p1/shares`);

    fetchMock.mockResolvedValueOnce(jsonResponse({}, 204));
    await revokeShare('p1', 'abc');
    const [, init] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(fetchMock.mock.calls[1][0]).toBe(`${API_BASE}/api/projects/p1/shares/abc`);
    expect(init.method).toBe('DELETE');
  });

  it('getSharedProject reads the public link', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ id: 'p1', name: 'Poster', sceneGraph: scene, permission: 'view' }, 200));

    const out = await getSharedProject('tok');

    expect(fetchMock.mock.calls[0][0]).toBe(`${API_BASE}/api/share/tok`);
    expect(out.permission).toBe('view');
  });

  it('updateSharedProject PATCHes the scene graph', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ id: 'p1', sceneGraph: scene, permission: 'edit' }, 200));

    await updateSharedProject('tok', scene);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/share/tok`);
    expect(init.method).toBe('PATCH');
    expect(JSON.parse(String(init.body))).toEqual({ sceneGraph: scene });
  });

  it('createTemplate posts scene graph with auth', async () => {
    setToken('tok');
    fetchMock.mockResolvedValueOnce(jsonResponse({ id: 't1', name: 'Poster layout', sceneGraph: scene }, 201));

    const out = await createTemplate('Poster layout', scene);

    expect(fetchMock.mock.calls[0][0]).toBe(`${API_BASE}/api/templates`);
    expect(JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body))).toEqual({ name: 'Poster layout', sceneGraph: scene });
    expect(out.name).toBe('Poster layout');
  });

  it('listTemplates and getTemplate are public reads', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse([{ id: 't1' }], 200));
    await listTemplates();
    expect(fetchMock.mock.calls[0][0]).toBe(`${API_BASE}/api/templates`);

    fetchMock.mockResolvedValueOnce(jsonResponse({ id: 't1', sceneGraph: scene }, 200));
    await getTemplate('t1');
    expect(fetchMock.mock.calls[1][0]).toBe(`${API_BASE}/api/templates/t1`);
    const headers = new Headers((fetchMock.mock.calls[1][1] as RequestInit)?.headers);
    expect(headers.get('Authorization')).toBeNull();
  });

  it('deleteTemplate requires owner auth and targets DELETE', async () => {
    setToken('tok');
    fetchMock.mockResolvedValueOnce(jsonResponse({}, 204));
    await deleteTemplate('t1');
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/templates/t1`);
    expect(init.method).toBe('DELETE');
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer tok');
  });

  it('createBatch posts uploadIds and getBatch reads status', async () => {
    setToken('tok');
    fetchMock.mockResolvedValueOnce(jsonResponse({ id: 'b1', jobs: [{ id: 'j1', status: 'queued' }] }, 201));
    const batch = await createBatch(['u1', 'u2']);
    expect(fetchMock.mock.calls[0][0]).toBe(`${API_BASE}/api/batches`);
    expect(JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body))).toEqual({ uploadIds: ['u1', 'u2'] });
    expect(batch.id).toBe('b1');

    fetchMock.mockResolvedValueOnce(jsonResponse({ id: 'b1', jobs: [{ id: 'j1', status: 'done' }] }, 200));
    await getBatch('b1');
    expect(fetchMock.mock.calls[1][0]).toBe(`${API_BASE}/api/batches/b1`);
  });

  it('shareUrl builds an absolute origin link', () => {
    Object.defineProperty(window, 'location', { value: { origin: 'https://app.example.com' }, writable: true });
    expect(shareUrl('tok')).toBe('https://app.example.com/share/tok');
    expect(getToken()).toBeNull();
  });
});

function jsonResponse(payload: unknown, status: number): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(payload),
  } as unknown as Response;
}