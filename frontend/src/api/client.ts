import { ApiValidationErrorItem } from '../types/api';

/**
 * Custom error thrown when the AnalytixFlow API returns an HTTP 4xx or 5xx status.
 * Preserves the exact status code, parsed error details, and correlation identifier.
 */
export class ApiError extends Error {
  public readonly status: number;
  public readonly detail: string | ApiValidationErrorItem[];
  public readonly correlationId?: string;

  constructor(
    status: number,
    detail: string | ApiValidationErrorItem[],
    message?: string,
    correlationId?: string
  ) {
    const formattedMessage =
      message ||
      (typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => d.msg).join('; ')
          : `HTTP Error ${status}`);
    super(formattedMessage);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
    this.correlationId = correlationId;
  }
}

/**
 * Custom error thrown when the network request fails before reaching or receiving
 * a response from the API server (e.g. connection refused, offline, DNS failure).
 */
export class NetworkError extends Error {
  public readonly originalError: Error;

  constructor(originalError: Error) {
    super(`Error de conexión con el servidor: ${originalError.message || 'Fallo de red'}`);
    this.name = 'NetworkError';
    this.originalError = originalError;
  }
}

export interface RequestOptions extends Omit<RequestInit, 'headers'> {
  headers?: Record<string, string>;
  correlationId?: string;
  idempotencyKey?: string;
  params?: Record<string, string | number | boolean | undefined>;
}

/**
 * Generate a random correlation ID conforming to backend constraints.
 */
export function generateCorrelationId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return `corr-${crypto.randomUUID().slice(0, 16)}`;
  }
  return `corr-${Math.random().toString(36).substring(2, 10)}`;
}

export class ApiClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string = '/api/v1') {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
  }

  private buildUrl(path: string, params?: Record<string, string | number | boolean | undefined>): string {
    const cleanPath = path.startsWith('/') ? path : `/${path}`;
    const url = `${this.baseUrl}${cleanPath}`;
    if (!params) {
      return url;
    }
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) {
        searchParams.append(key, String(value));
      }
    }
    const query = searchParams.toString();
    return query ? `${url}?${query}` : url;
  }

  public async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const correlationId = options.correlationId || generateCorrelationId();
    const headers: Record<string, string> = {
      Accept: 'application/json',
      'X-Correlation-ID': correlationId,
      ...options.headers,
    };

    // Attach Idempotency-Key ONLY when explicitly provided for mutations
    if (options.idempotencyKey) {
      headers['Idempotency-Key'] = options.idempotencyKey;
    }

    // Set Content-Type: application/json if sending a JSON body and not already set
    if (
      options.body &&
      typeof options.body === 'string' &&
      !headers['Content-Type']
    ) {
      headers['Content-Type'] = 'application/json';
    }

    const url = this.buildUrl(path, options.params);

    let response: Response;
    try {
      response = await fetch(url, {
        ...options,
        headers,
      });
    } catch (err: unknown) {
      const error = err instanceof Error ? err : new Error(String(err));
      throw new NetworkError(error);
    }

    const returnedCorrelationId =
      response.headers.get('X-Correlation-ID') || correlationId;

    if (!response.ok) {
      let detail: string | ApiValidationErrorItem[] = `HTTP error ${response.status}`;
      try {
        const errorJson = await response.json();
        if (errorJson && errorJson.detail !== undefined) {
          detail = errorJson.detail;
        }
      } catch {
        try {
          const errorText = await response.text();
          if (errorText) {
            detail = errorText;
          }
        } catch {
          // Keep default detail
        }
      }

      throw new ApiError(
        response.status,
        detail,
        undefined,
        returnedCorrelationId
      );
    }

    // Handle 204 No Content or empty bodies safely
    if (response.status === 204) {
      return null as T;
    }

    const contentLength = response.headers.get('content-length');
    if (contentLength === '0') {
      return null as T;
    }

    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      return (await response.json()) as T;
    }

    return (await response.text()) as unknown as T;
  }

  public get<T>(path: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(path, { ...options, method: 'GET' });
  }

  public post<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    const isJson = body !== undefined && !(body instanceof FormData) && !(body instanceof Blob);
    const serializedBody = isJson ? JSON.stringify(body) : (body as BodyInit | undefined);
    return this.request<T>(path, {
      ...options,
      method: 'POST',
      body: serializedBody,
    });
  }

  public put<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    const isJson = body !== undefined && !(body instanceof FormData) && !(body instanceof Blob);
    const serializedBody = isJson ? JSON.stringify(body) : (body as BodyInit | undefined);
    return this.request<T>(path, {
      ...options,
      method: 'PUT',
      body: serializedBody,
    });
  }

  public delete<T>(path: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(path, { ...options, method: 'DELETE' });
  }
}

export const apiClient = new ApiClient();
