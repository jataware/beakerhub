import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { client } from '@/utils/fetch';

describe('fetch client base URL', () => {
  const nativeFetch = vi.fn();

  beforeEach(() => {
    client.setBaseUrl('/');
    nativeFetch.mockResolvedValue(new Response());
    vi.stubGlobal('fetch', nativeFetch);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it('uses root paths when the base is root', async () => {
    await client.fetch('/api/user?test=1');
    expect(nativeFetch.mock.calls[0][0]).toBe(`${window.location.origin}/api/user?test=1`);
  });

  it('prefixes paths with the configured base', async () => {
    client.setBaseUrl('/beaker/');
    await client.fetch('/api/user');
    expect(nativeFetch.mock.calls[0][0]).toBe(`${window.location.origin}/beaker/api/user`);
  });

  it('supports an explicit base without forwarding it to fetch', async () => {
    await client.fetch('/api/user', { baseUrl: '/other/', method: 'GET' });
    expect(nativeFetch.mock.calls[0][0]).toBe(`${window.location.origin}/other/api/user`);
    expect(nativeFetch.mock.calls[0][1]).toEqual({ method: 'GET', headers: {} });
  });

  it('leaves already-prefixed URLs alone when skipBase is set', async () => {
    client.setBaseUrl('/beaker/');
    await client.fetch('/beaker/api/user', { skipBase: true });
    expect(nativeFetch.mock.calls[0][0]).toBe(`${window.location.origin}/beaker/api/user`);
    expect(nativeFetch.mock.calls[0][1]).toEqual({ headers: {} });
  });
});
