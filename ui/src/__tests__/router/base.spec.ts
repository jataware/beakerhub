import { describe, expect, it } from 'vitest';
import { createRouter } from '@/router';

describe('router base URL', () => {
  it('uses the runtime prefix without modifying routes across instances', () => {
    const first = createRouter({ pathPrefix: '/beaker/' });
    const second = createRouter({ pathPrefix: '/other/' });
    const root = createRouter({ pathPrefix: '/' });

    expect(first.resolve({ name: 'login' }).href).toBe('/beaker/login');
    expect(second.resolve({ name: 'login' }).href).toBe('/other/login');
    expect(root.resolve({ name: 'login' }).href).toBe('/login');
  });
});
