/**
 * Sense Loop API Client
 * Uses SL session tokens instead of OW tokens
 * Redirects to /sl/login on 401 instead of /login
 */

import { API_CONFIG } from './config';
import { ApiError } from '../errors/api-error';
import { getSlToken, clearSlSession } from '../auth/sl-session';

const SL_LOGIN_ROUTE = '/sl/login';

interface RequestOptions extends RequestInit {
  timeout?: number;
  retries?: number;
  params?: Record<string, unknown>;
}

async function fetchWithRetry(
  url: string,
  options: RequestOptions = {},
  attempt: number = 0
): Promise<Response> {
  const {
    timeout = API_CONFIG.timeout,
    retries = API_CONFIG.retryAttempts,
    ...fetchOptions
  } = options;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      ...fetchOptions,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    // Retry on 5xx errors
    if (response.status >= 500 && attempt < retries) {
      await delay(API_CONFIG.retryDelay * (attempt + 1));
      return fetchWithRetry(url, options, attempt + 1);
    }

    return response;
  } catch (error: unknown) {
    clearTimeout(timeoutId);

    if (error instanceof Error && error.name === 'AbortError') {
      throw ApiError.timeout();
    }

    const message = error instanceof Error ? error.message : 'Network error';
    throw ApiError.networkError(message);
  }
}

export const slApiClient = {
  async request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    let url = `${API_CONFIG.baseUrl}${endpoint}`;
    const token = getSlToken();

    if (options.params) {
      const searchParams = new URLSearchParams();
      Object.entries(options.params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          if (Array.isArray(value)) {
            value.forEach((item) => searchParams.append(key, String(item)));
          } else {
            searchParams.append(key, String(value));
          }
        }
      });
      const queryString = searchParams.toString();
      if (queryString) {
        url += (url.includes('?') ? '&' : '?') + queryString;
      }
    }

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    // Remove params from options passed to fetch
    const { params: _params, ...fetchOptions } = options;

    try {
      const response = await fetchWithRetry(url, {
        ...fetchOptions,
        headers,
      });

      if (response.status === 401) {
        clearSlSession();
        if (typeof window !== 'undefined') {
          window.location.href = SL_LOGIN_ROUTE;
        }
        throw ApiError.fromResponse(response);
      }

      let data: unknown;
      const contentType = response.headers.get('content-type');

      if (
        response.status === 204 ||
        response.headers.get('content-length') === '0'
      ) {
        data = undefined;
      } else if (contentType?.includes('application/json')) {
        data = await response.json();
      } else {
        data = await response.text();
      }

      if (!response.ok) {
        throw ApiError.fromResponse(response, data);
      }

      return data as T;
    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }
      throw ApiError.networkError((error as Error).message);
    }
  },

  get<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'GET' });
  },

  post<T>(
    endpoint: string,
    body?: unknown,
    options?: RequestOptions
  ): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    });
  },

  patch<T>(
    endpoint: string,
    body?: unknown,
    options?: RequestOptions
  ): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PATCH',
      body: body ? JSON.stringify(body) : undefined,
    });
  },

  put<T>(
    endpoint: string,
    body?: unknown,
    options?: RequestOptions
  ): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
    });
  },

  delete<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'DELETE' });
  },
};

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Public API Client for SL auth endpoints
 * Does NOT redirect on 401 - lets the calling code handle auth errors
 * Use this for login, forgot-password, reset-password, accept-invite
 */
export const slPublicApiClient = {
  async post<T>(endpoint: string, body?: unknown): Promise<T> {
    const url = `${API_CONFIG.baseUrl}${endpoint}`;

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    try {
      const response = await fetchWithRetry(url, {
        method: 'POST',
        headers,
        body: body ? JSON.stringify(body) : undefined,
      });

      let data: unknown;
      const contentType = response.headers.get('content-type');

      if (
        response.status === 204 ||
        response.headers.get('content-length') === '0'
      ) {
        data = undefined;
      } else if (contentType?.includes('application/json')) {
        data = await response.json();
      } else {
        data = await response.text();
      }

      if (!response.ok) {
        throw ApiError.fromResponse(response, data);
      }

      return data as T;
    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }
      throw ApiError.networkError((error as Error).message);
    }
  },
};

export { ApiError };
