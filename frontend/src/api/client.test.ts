import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ApiClient, ApiError, NetworkError } from './client';

describe('ApiClient', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('generates and attaches X-Correlation-ID automatically when not provided', async () => {
    let capturedHeaders: Record<string, string> = {};
    globalThis.fetch = vi.fn().mockImplementation((_url, init) => {
      capturedHeaders = init?.headers as Record<string, string>;
      return Promise.resolve(
        new Response(JSON.stringify({ status: 'ok' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    const client = new ApiClient('/api/v1');
    const result = await client.get<{ status: string }>('/health');

    expect(result).toEqual({ status: 'ok' });
    expect(capturedHeaders['X-Correlation-ID']).toBeDefined();
    expect(capturedHeaders['X-Correlation-ID']).toMatch(/^corr-[a-zA-Z0-9_-]+$/);
    expect(capturedHeaders['Idempotency-Key']).toBeUndefined();
  });

  it('preserves user-supplied correlationId and sends it in X-Correlation-ID', async () => {
    let capturedHeaders: Record<string, string> = {};
    globalThis.fetch = vi.fn().mockImplementation((_url, init) => {
      capturedHeaders = init?.headers as Record<string, string>;
      return Promise.resolve(
        new Response(JSON.stringify({ status: 'ok' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    const client = new ApiClient('/api/v1');
    await client.get('/health', { correlationId: 'corr-custom-123' });

    expect(capturedHeaders['X-Correlation-ID']).toBe('corr-custom-123');
  });

  it('attaches Idempotency-Key ONLY when explicitly provided in request options', async () => {
    let capturedHeaders: Record<string, string> = {};
    globalThis.fetch = vi.fn().mockImplementation((_url, init) => {
      capturedHeaders = init?.headers as Record<string, string>;
      return Promise.resolve(
        new Response(JSON.stringify({ created: true }), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    const client = new ApiClient('/api/v1');
    await client.post('/projects', { name: 'Test' }, { idempotencyKey: 'key-idempotent-abc' });

    expect(capturedHeaders['Idempotency-Key']).toBe('key-idempotent-abc');
  });

  it('handles empty responses (204 No Content) returning null without error', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(null, {
        status: 204,
      })
    );

    const client = new ApiClient('/api/v1');
    const result = await client.delete('/projects/123');

    expect(result).toBeNull();
  });

  it('distinguishes network errors and throws NetworkError', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));

    const client = new ApiClient('/api/v1');

    await expect(client.get('/health')).rejects.toThrowError(NetworkError);
    await expect(client.get('/health')).rejects.toThrowError(/Fallo de red|Failed to fetch/);
  });

  it('distinguishes API HTTP errors and throws ApiError with status and parsed detail', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Project not found' }), {
        status: 404,
        headers: {
          'Content-Type': 'application/json',
          'X-Correlation-ID': 'corr-resp-404',
        },
      })
    );

    const client = new ApiClient('/api/v1');

    try {
      await client.get('/projects/p-999');
      expect.unreachable('Should have thrown ApiError');
    } catch (err: unknown) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(404);
      expect(apiErr.detail).toBe('Project not found');
      expect(apiErr.correlationId).toBe('corr-resp-404');
    }
  });

  it('formats validation errors array from Pydantic into readable message in ApiError', async () => {
    const pydanticDetail = [
      { loc: ['body', 'company_name'], msg: 'Field required', type: 'missing' },
      { loc: ['body', 'owner_id'], msg: 'String should have at least 1 character', type: 'string_too_short' },
    ];

    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: pydanticDetail }), {
        status: 422,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    const client = new ApiClient('/api/v1');

    try {
      await client.post('/projects', {});
      expect.unreachable('Should have thrown ApiError');
    } catch (err: unknown) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(422);
      expect(apiErr.message).toBe('Field required; String should have at least 1 character');
      expect(Array.isArray(apiErr.detail)).toBe(true);
    }
  });
});
