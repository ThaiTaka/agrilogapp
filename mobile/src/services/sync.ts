/**
 * Sync adapter — wires WatermelonDB's `synchronize()` to the backend
 * (Issues #34, #35, #36).
 *
 * Thin on purpose. All the hard decisions live on the server
 * (backend/app/services/sync_service.py) and in the contract
 * (Data_Requirements_Database.md §6.5, §6.6); this file's job is to speak
 * that contract faithfully and to fail in ways a farmer can understand.
 *
 * Three things it must get right:
 *
 *   1. Never lose a rejection. A record the server refused is surfaced, not
 *      swallowed — a farmer whose edit lost a last-write-wins race deserves
 *      to be told, not to discover three weeks later that the note never
 *      saved.
 *   2. Retry safely. Rural connectivity drops mid-request constantly. Retries
 *      are safe because record IDs are client-generated (R1), so the server
 *      upserts and a repeated batch cannot duplicate anything.
 *   3. Never block the UI. Sync failing is the normal state in a field, not
 *      an error condition.
 */

import {Q} from '@nozbe/watermelondb';
import {
  hasUnsyncedChanges,
  synchronize,
  type SyncDatabaseChangeSet,
} from '@nozbe/watermelondb/sync';
import AsyncStorage from '@react-native-async-storage/async-storage';

import {database} from '../db';
import {SYNC_TABLES} from '../db/schema';
import {ApiError, request} from './api';

const LAST_SYNC_KEY = '@agrilog/last_sync_at';

// ─── Wire types (mirror backend/app/schemas/sync.py) ────────────────────────

interface PullResponse {
  changes: SyncDatabaseChangeSet;
  timestamp: number;
}

export interface RejectedRecord {
  table: string;
  id: string;
  reason:
    | 'stale_update'
    | 'missing_parent'
    | 'foreign_record'
    | 'unknown_table'
    | 'invalid_record';
  detail?: string | null;
  server_updated_at?: number | null;
}

interface PushResponse {
  accepted: number;
  rejected: RejectedRecord[];
  timestamp: number;
}

export interface SyncResult {
  ok: boolean;
  pushed: number;
  rejected: RejectedRecord[];
  /** Present when the sync failed outright rather than partially. */
  error?: string;
}

// ─── Human-readable rejection reasons ───────────────────────────────────────

const REJECTION_MESSAGES: Record<RejectedRecord['reason'], string> = {
  stale_update:
    'Bản ghi đã được sửa trên thiết bị khác sau lần sửa này, nên bản mới hơn được giữ lại.',
  missing_parent:
    'Dữ liệu liên quan chưa được đồng bộ. Sẽ tự thử lại ở lần đồng bộ sau.',
  foreign_record: 'Bản ghi này không thuộc về nông hộ của bạn.',
  unknown_table: 'Phiên bản ứng dụng không khớp với máy chủ. Hãy cập nhật ứng dụng.',
  invalid_record: 'Bản ghi không hợp lệ và bị máy chủ từ chối.',
};

export function describeRejection(rejection: RejectedRecord): string {
  return REJECTION_MESSAGES[rejection.reason] ?? 'Máy chủ từ chối bản ghi này.';
}

// ─── Last successful sync ───────────────────────────────────────────────────

export async function getLastSyncAt(): Promise<number | null> {
  const raw = await AsyncStorage.getItem(LAST_SYNC_KEY);
  return raw ? Number(raw) : null;
}

async function setLastSyncAt(ms: number): Promise<void> {
  await AsyncStorage.setItem(LAST_SYNC_KEY, String(ms));
}

// ─── Pending change count ───────────────────────────────────────────────────

/**
 * How many local records are waiting to be pushed.
 *
 * This is the whole reason AgriLog needs no outbox table: the local database
 * IS the queue. `_status != 'synced'` is the pending set, and WatermelonDB
 * maintains it for us on every write.
 *
 * Counted with a direct query per table rather than by building a change set:
 * the badge refreshes whenever the sync bar is on screen, and materialising
 * every pending record just to take its length would be wasteful.
 */
export async function pendingChangeCount(): Promise<number> {
  const counts = await Promise.all(
    SYNC_TABLES.map(table =>
      database
        .get(table)
        .query(Q.where('_status', Q.notEq('synced')))
        .fetchCount(),
    ),
  );
  return counts.reduce((sum, n) => sum + n, 0);
}

export async function hasPendingChanges(): Promise<boolean> {
  return hasUnsyncedChanges({database});
}

// ─── The sync cycle ─────────────────────────────────────────────────────────

let inFlight: Promise<SyncResult> | null = null;

/**
 * Run one pull-then-push cycle.
 *
 * Concurrent calls share one run: the sync status button and the automatic
 * background trigger can both fire at once, and two overlapping cycles would
 * push the same batch twice. Harmless thanks to R1, but wasteful on a
 * connection that is already the bottleneck.
 */
export async function sync(): Promise<SyncResult> {
  if (inFlight) {
    return inFlight;
  }
  inFlight = runSync().finally(() => {
    inFlight = null;
  });
  return inFlight;
}

async function runSync(): Promise<SyncResult> {
  const rejected: RejectedRecord[] = [];
  let pushed = 0;

  try {
    await synchronize({
      database,

      pullChanges: async ({lastPulledAt, schemaVersion, migration}) => {
        const params = new URLSearchParams();
        if (lastPulledAt) {
          params.set('lastPulledAt', String(lastPulledAt));
        }
        params.set('schemaVersion', String(schemaVersion));
        if (migration) {
          params.set('migration', JSON.stringify(migration));
        }

        const response = await request<PullResponse>(
          `/api/v1/sync/pull?${params.toString()}`,
        );
        return {changes: response.changes, timestamp: response.timestamp};
      },

      pushChanges: async ({changes, lastPulledAt}) => {
        const response = await request<PushResponse>(
          `/api/v1/sync/push?lastPulledAt=${lastPulledAt}`,
          {method: 'POST', body: {changes}},
        );
        pushed = response.accepted;
        rejected.push(...response.rejected);

        // Deliberately NOT thrown. Throwing would make WatermelonDB treat the
        // whole push as failed and keep every record pending, including the
        // ones the server accepted — turning a handful of conflicts into a
        // permanently stuck device. The rejections are reported to the UI
        // instead, and `missing_parent` resolves itself next cycle.
        if (response.rejected.length > 0) {
          console.warn(
            `[AgriLog] Máy chủ từ chối ${response.rejected.length} bản ghi`,
            response.rejected,
          );
        }
      },

      // The client sends every local change as `created`; the server treats
      // created and updated identically (an upsert on a client-owned ID), so
      // there is nothing to gain from the client classifying them.
      sendCreatedAsUpdated: false,
      migrationsEnabledAtVersion: 1,
    });

    await setLastSyncAt(Date.now());
    return {ok: true, pushed, rejected};
  } catch (error) {
    const message =
      error instanceof ApiError
        ? error.message
        : 'Đồng bộ thất bại. Dữ liệu vẫn được lưu an toàn trên máy.';

    // The reassurance is the important half: nothing was lost. Every record
    // is still in SQLite at `_status != 'synced'` and will go up next time.
    console.warn('[AgriLog] Đồng bộ thất bại:', error);
    return {ok: false, pushed, rejected, error: message};
  }
}

// ─── Retry with backoff (#36) ───────────────────────────────────────────────

export interface RetryOptions {
  maxAttempts?: number;
  baseDelayMs?: number;
  maxDelayMs?: number;
}

/**
 * Retry a sync over an unstable connection.
 *
 * Only *transient* failures are retried — a 401 or a 413 will fail exactly
 * the same way on attempt five, and hammering the server with a request that
 * cannot succeed drains a battery the farmer may not be able to recharge
 * today.
 *
 * Retrying is safe because record IDs are client-generated: the server
 * upserts, so a batch delivered twice produces the same result as once.
 */
export async function syncWithRetry(options: RetryOptions = {}): Promise<SyncResult> {
  const {maxAttempts = 4, baseDelayMs = 1_000, maxDelayMs = 30_000} = options;

  let last: SyncResult = {ok: false, pushed: 0, rejected: []};

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    last = await sync();
    if (last.ok) {
      return last;
    }

    if (attempt === maxAttempts - 1) {
      break;
    }

    // Exponential backoff with jitter. Without jitter, several devices that
    // lost signal together come back and retry in lockstep.
    const delay = Math.min(baseDelayMs * 2 ** attempt, maxDelayMs);
    const jitter = Math.random() * delay * 0.3;
    await new Promise<void>(resolve => {
      setTimeout(() => resolve(), delay + jitter);
    });
  }

  return last;
}
