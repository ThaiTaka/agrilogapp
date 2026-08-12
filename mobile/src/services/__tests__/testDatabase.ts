/**
 * A real, in-memory WatermelonDB for service tests.
 *
 * LokiJS rather than SQLite: the SQLite adapter binds to a native library
 * that does not exist in Node. LokiJS runs the SAME query and writer layers,
 * so the logic under test — reconciliation, stock arithmetic, expense
 * generation — is exercised for real rather than against a mock.
 *
 * This matters more than it might sound. The stock-restore invariants are
 * about what happens across several writes to related tables; a mocked
 * database would happily confirm whatever the implementation does, which is
 * precisely the bug these tests exist to catch.
 */

import {Database} from '@nozbe/watermelondb';
import LokiJSAdapter from '@nozbe/watermelondb/adapters/lokijs';

import {modelClasses} from '../../db/models';
import {mySchema} from '../../db/schema';

export function createTestDatabase(): Database {
  const adapter = new LokiJSAdapter({
    schema: mySchema,
    useWebWorker: false,
    useIncrementalIndexedDB: false,
    dbName: `agrilog-test-${Math.random().toString(36).slice(2)}`,
  });

  return new Database({adapter, modelClasses});
}
