/**
 * WatermelonDB singleton — the app's source of truth for writes (Issue #16).
 *
 * Nothing in the UI ever waits on the network. Every create/update/delete
 * commits to SQLite inside a `writer` block and returns immediately; screens
 * re-render from observable queries, not from an HTTP response.
 */

import 'react-native-get-random-values'; // must precede any uuid use

import {Database} from '@nozbe/watermelondb';
import SQLiteAdapter from '@nozbe/watermelondb/adapters/sqlite';
import {setGenerator} from '@nozbe/watermelondb/utils/common/randomId';
import {v4 as uuidv4} from 'uuid';

import migrations from './migrations';
import {modelClasses} from './models';
import {mySchema} from './schema';

/**
 * Rule R1 — record IDs are generated HERE, on the device, before the network
 * is ever consulted. That is what makes a retried sync safe: the server
 * upserts on a key the client already owns, so re-sending a batch after a
 * dropped connection cannot create a duplicate.
 *
 * WatermelonDB's default generator produces a 16-character random string. We
 * override it so mobile IDs are RFC-4122 UUIDs, matching what the backend's
 * seed script and any future web client produce — the ID format is part of
 * the sync contract, not an implementation detail.
 */
setGenerator(() => uuidv4());

const adapter = new SQLiteAdapter({
  schema: mySchema,
  migrations,
  // JSI gives synchronous native calls, which keeps list scrolling smooth on
  // the low-end Android phones this app targets.
  jsi: true,
  dbName: 'agrilog',
  onSetUpError: error => {
    // Reaching here means the local database could not be opened at all —
    // the app is unusable, and silently swallowing it would present as a
    // blank screen with no explanation.
    console.error('[AgriLog] Không mở được cơ sở dữ liệu cục bộ:', error);
  },
});

export const database = new Database({
  adapter,
  modelClasses,
});

export {mySchema, SCHEMA_VERSION, SYNC_TABLES} from './schema';
export * from './models';
