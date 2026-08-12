/**
 * HTTP client for the AgriLog backend.
 *
 * Used ONLY by auth and by the sync engine. No screen ever calls this
 * directly — screens read and write WatermelonDB, and sync reconciles later.
 * If a feature needs `api` on the render path, that feature is not
 * offline-first and the design is wrong.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import {v4 as uuidv4} from 'uuid';

/**
 * 10.0.2.2 is how the Android emulator reaches the host machine; 127.0.0.1
 * inside the emulator is the emulator itself. On a physical device this must
 * be the host's LAN address.
 */
export const API_BASE_URL = 'http://10.0.2.2:8000';

const ACCESS_TOKEN_KEY = '@agrilog/access_token';
const REFRESH_TOKEN_KEY = '@agrilog/refresh_token';
const DEVICE_ID_KEY = '@agrilog/device_id';

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public detail?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }

  /** True when retrying later could plausibly succeed — drives sync backoff. */
  get isTransient(): boolean {
    return this.status === 0 || this.status === 408 || this.status >= 500;
  }
}

// ─── Token storage ──────────────────────────────────────────────────────────

export async function getAccessToken(): Promise<string | null> {
  return AsyncStorage.getItem(ACCESS_TOKEN_KEY);
}

export async function getRefreshToken(): Promise<string | null> {
  return AsyncStorage.getItem(REFRESH_TOKEN_KEY);
}

export async function storeTokens(access: string, refresh: string): Promise<void> {
  // async-storage v3 replaced the tuple-array multiSet/multiRemove with
  // record-shaped setMany / removeMany.
  await AsyncStorage.setMany({
    [ACCESS_TOKEN_KEY]: access,
    [REFRESH_TOKEN_KEY]: refresh,
  });
}

export async function clearTokens(): Promise<void> {
  await AsyncStorage.removeMany([ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY]);
}

/**
 * A stable per-installation identifier, used for sync auditing.
 *
 * Generated once and kept: it is how `sync_sessions` attributes a conflict to
 * a device, which is the data Issue #40 needs.
 */
export async function getDeviceId(): Promise<string> {
  let id = await AsyncStorage.getItem(DEVICE_ID_KEY);
  if (!id) {
    id = uuidv4();
    await AsyncStorage.setItem(DEVICE_ID_KEY, id);
  }
  return id;
}

// ─── Requests ───────────────────────────────────────────────────────────────

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  body?: unknown;
  auth?: boolean;
  timeoutMs?: number;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const {method = 'GET', body, auth = true, timeoutMs = 30_000} = options;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Device-Id': await getDeviceId(),
  };

  if (auth) {
    const token = await getAccessToken();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
  }

  // A rural connection can hang rather than fail. Without an explicit
  // timeout, a sync attempt waits forever and the "Đang đồng bộ…" spinner
  // never resolves.
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (error) {
    // Status 0 means "never reached the server" — a normal condition in a
    // field, not an error worth alarming the farmer about.
    throw new ApiError(0, 'Không kết nối được máy chủ', error);
  } finally {
    clearTimeout(timer);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  const payload = text ? JSON.parse(text) : undefined;

  if (!response.ok) {
    const detail =
      payload && typeof payload === 'object' && 'detail' in payload
        ? String((payload as {detail: unknown}).detail)
        : `Lỗi máy chủ (${response.status})`;
    throw new ApiError(response.status, detail, payload);
  }

  return payload as T;
}
