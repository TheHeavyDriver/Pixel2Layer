import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  API_BASE,
  createProject,
  deleteProject,
  getCurrentUser,
  getProject,
  getToken,
  listProjects,
  listVersions,
  login,
  logout,
  register,
  restoreVersion,
  saveVersion,
  setToken,
  updateProject,
} from '@/lib/api';

describe('auth + projects api client', () => {
  const fetchMock = vi.fn();
  globalThis.fetch = fetchMock as unknown as typeof fetch;

  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    fetchMock.mockReset();
  });

  it('register stores the token and returns the user', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ token: 'tok-1', user: { id: 'u1', email: 'a@b.co', name: null } }, 201),
    );

    const out = await register({ email: 'a@b.co', password: 'password123' });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/auth/register`);
    expect(JSON.parse(String(init.body))).toEqual({ email: 'a@b.co', password: 'password123' });
    expect(out.user.email).toBe('a@b.co');
    expect(getToken()).toBe('tok-1');
  });

  it('login posts credentials and stores the token', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ token: 'tok-2', user: { id: 'u2', email: 'x@y.co', name: 'X' } }, 200),
    );

    const out = await login({ email: 'x@y.co', password: 'password123' });

    expect(fetchMock.mock.calls[0][0]).toBe(`${API_BASE}/api/auth/login`);
    expect(out.user.name).toBe('X');
    expect(getToken()).toBe('tok-2');
  });

  it('getCurrentUser returns null without a token', async () => {
    expect(await getCurrentUser()).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('getCurrentUser calls /me with the bearer token', async () => {
    setToken('tok-3');
    fetchMock.mockResolvedValueOnce(jsonResponse({ id: 'u3', email: 'me@x.co', name: null }, 200));

    const user = await getCurrentUser();

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/auth/me`);
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer tok-3');
    expect(user?.email).toBe('me@x.co');
  });

  it('logout clears the token', async () => {
    setToken('tok-4');
    logout();
    expect(getToken()).toBeNull();
  });

  it('createProject posts a bearer-authed JSON body', async () => {
    setToken('tok-5');
    const scene = { schemaVersion: 1, layers: [] };
    fetchMock.mockResolvedValueOnce(jsonResponse({ id: 'p1', name: 'Poster', sceneGraph: scene }, 201));

    const out = await createProject('Poster', scene);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/projects`);
    expect(JSON.parse(String(init.body))).toEqual({ name: 'Poster', sceneGraph: scene });
    const headers = new Headers(init.headers);
    expect(headers.get('Authorization')).toBe('Bearer tok-5');
    expect(headers.get('Content-Type')).toBe('application/json');
    expect(out.name).toBe('Poster');
  });

  it('listProjects forwards the token', async () => {
    setToken('tok-6');
    fetchMock.mockResolvedValueOnce(jsonResponse([{ id: 'p1', name: 'A' }], 200));

    const out = await listProjects();

    expect(fetchMock.mock.calls[0][0]).toBe(`${API_BASE}/api/projects`);
    expect(new Headers((fetchMock.mock.calls[0][1] as RequestInit).headers).get('Authorization')).toBe('Bearer tok-6');
    expect(out).toHaveLength(1);
  });

  it('getProject / updateProject / deleteProject target the right paths', async () => {
    setToken('tok-7');
    fetchMock.mockResolvedValueOnce(jsonResponse({ id: 'p1', sceneGraph: { layers: [] } }, 200));
    await getProject('p1');
    expect(fetchMock.mock.calls[0][0]).toBe(`${API_BASE}/api/projects/p1`);

    fetchMock.mockResolvedValueOnce(jsonResponse({ id: 'p1', name: 'Renamed' }, 200));
    await updateProject('p1', { name: 'Renamed' });
    const [, init] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(init.method).toBe('PATCH');
    expect(JSON.parse(String(init.body))).toEqual({ name: 'Renamed' });

    fetchMock.mockResolvedValueOnce(jsonResponse({}, 204));
    await deleteProject('p1');
    const [url2, init2] = fetchMock.mock.calls[2] as [string, RequestInit];
    expect(url2).toBe(`${API_BASE}/api/projects/p1`);
    expect(init2.method).toBe('DELETE');
  });

  it('saveVersion / listVersions / restoreVersion hit version endpoints', async () => {
    setToken('tok-8');
    const scene = { layers: [] };
    fetchMock.mockResolvedValueOnce(jsonResponse({ id: 'v1', versionNo: 1, sceneGraph: scene }, 201));
    await saveVersion('p1', scene, 'Version 1');
    expect(fetchMock.mock.calls[0][0]).toBe(`${API_BASE}/api/projects/p1/versions`);

    fetchMock.mockResolvedValueOnce(jsonResponse([], 200));
    await listVersions('p1');
    expect(fetchMock.mock.calls[1][0]).toBe(`${API_BASE}/api/projects/p1/versions`);

    fetchMock.mockResolvedValueOnce(jsonResponse({ id: 'p1', sceneGraph: scene }, 200));
    await restoreVersion('p1', 1);
    const [url, init] = fetchMock.mock.calls[2] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/projects/p1/versions/1/restore`);
    expect(init.method).toBe('POST');
  });

  it('clears the stored token when /me returns 401', async () => {
    setToken('stale');
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: 'invalid token' }, 401));

    const user = await getCurrentUser();

    expect(user).toBeNull();
    expect(getToken()).toBeNull();
  });

  it('project calls throw descriptive errors on failure', async () => {
    setToken('tok-9');
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: 'project not found' }, 404));

    await expect(getProject('nope')).rejects.toThrow('project not found');
  });
});

function jsonResponse(payload: unknown, status: number): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(payload),
  } as unknown as Response;
}