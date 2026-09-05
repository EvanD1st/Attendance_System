import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api';
import { useLoad } from './useLoad';

vi.mock('../api', () => ({
  api: { get: vi.fn() },
  errorMessage: () => 'Request failed',
}));

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}

describe('useLoad response ordering', () => {
  beforeEach(() => vi.clearAllMocks());

  it('does not let an older filter response overwrite the latest result', async () => {
    const old = deferred<{ data: string }>();
    vi.mocked(api.get).mockReturnValueOnce(old.promise).mockResolvedValueOnce({ data: 'new' });
    const { result, rerender } = renderHook(({ path }) => useLoad(path, ''), {
      initialProps: { path: '/old' },
    });
    rerender({ path: '/new' });
    await waitFor(() => expect(result.current.data).toBe('new'));
    await act(async () => old.resolve({ data: 'old' }));
    expect(result.current.data).toBe('new');
    expect(result.current.loading).toBe(false);
  });

  it('ignores late failures from a previous filter', async () => {
    const old = deferred<{ data: string }>();
    vi.mocked(api.get).mockReturnValueOnce(old.promise).mockResolvedValueOnce({ data: 'new' });
    const { result, rerender } = renderHook(({ path }) => useLoad(path, ''), {
      initialProps: { path: '/old' },
    });
    rerender({ path: '/new' });
    await waitFor(() => expect(result.current.data).toBe('new'));
    await act(async () => old.reject(new Error('old request failed')));
    expect(result.current.error).toBe('');
  });
});
