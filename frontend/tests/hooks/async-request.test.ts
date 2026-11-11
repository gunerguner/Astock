import { describe, expect, test } from 'vitest';
import useAsyncRequest from '@/hooks/async-request';

describe('useAsyncRequest', () => {
  test('starts loading and keeps the previous result after a later failure', async () => {
    let fail = false;
    const { loading, data, error, run } = useAsyncRequest(async () => {
      if (fail) throw new Error('boom');
      return { ok: true };
    });

    expect(loading.value).toBe(true);
    expect(data.value).toBeNull();

    await run();
    expect(data.value).toEqual({ ok: true });
    expect(loading.value).toBe(false);

    fail = true;
    await run();
    expect(data.value).toEqual({ ok: true });
    expect((error.value as Error).message).toBe('boom');
    expect(loading.value).toBe(false);
  });
});
