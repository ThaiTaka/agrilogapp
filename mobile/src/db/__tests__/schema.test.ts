/**
 * Schema parity — the mobile half of the shared sync contract (Issue #8).
 *
 * Reads the SAME docs/sync_contract.json that
 * backend/tests/test_sync_contract.py generates and asserts against, and
 * checks the WatermelonDB schema matches it column for column.
 *
 * Why this test exists: a field-name mismatch between the PostgreSQL schema
 * and the WatermelonDB schema is the highest-probability cause of a silent
 * sync bug in this project. Neither codebase can detect it alone — each is
 * internally consistent and perfectly happy while records quietly sync into
 * nothing. Making the agreement a committed artefact that both sides verify
 * is the only way to catch it, and it catches it in CI rather than in a
 * farmer's field.
 *
 * Runs without a device, an emulator, or a database.
 */

import {mySchema, SCHEMA_VERSION, SYNC_TABLES} from '../schema';

const contract = require('../../../../docs/sync_contract.json') as {
  schema_version: number;
  table_order: string[];
  server_only_columns: string[];
  tables: Record<string, string[]>;
};

/**
 * WatermelonDB stores `id` implicitly and adds `_status` / `_changed`
 * itself, so they never appear in tableSchema columns. The contract lists
 * `id` because the backend does have it as a real column.
 */
const IMPLICIT_COLUMNS = new Set(['id']);

function columnsOf(table: string): string[] {
  const tableSchema = mySchema.tables[table];
  if (!tableSchema) {
    throw new Error(`Bảng '${table}' không có trong schema WatermelonDB`);
  }
  return Object.keys(tableSchema.columns).sort();
}

function expectedColumnsOf(table: string): string[] {
  const cols = contract.tables[table];
  if (!cols) {
    throw new Error(`Bảng '${table}' không có trong sync_contract.json`);
  }
  return cols.filter(c => !IMPLICIT_COLUMNS.has(c)).sort();
}

describe('Hợp đồng đồng bộ: WatermelonDB ↔ PostgreSQL', () => {
  it('có đúng những bảng mà backend đồng bộ', () => {
    expect(Object.keys(mySchema.tables).sort()).toEqual(
      Object.keys(contract.tables).sort(),
    );
  });

  it('giữ đúng thứ tự phụ thuộc của backend', () => {
    // Both sides apply upserts in this order and deletes in reverse, so a
    // batch never inserts a child before its parent.
    expect([...SYNC_TABLES]).toEqual(contract.table_order);
  });

  it.each(Object.keys(contract.tables))('bảng %s khớp từng cột', table => {
    expect(columnsOf(table)).toEqual(expectedColumnsOf(table));
  });

  it('không bảng nào lộ cột chỉ-thuộc-máy-chủ', () => {
    // household_id, server_updated_at, deleted_at, last_device_id, name_key.
    // Sending household_id in particular would be pointless (the client knows
    // its household from the JWT) and would add a sixth chance to diverge.
    const leaks: string[] = [];
    for (const table of Object.keys(mySchema.tables)) {
      for (const col of columnsOf(table)) {
        if (contract.server_only_columns.includes(col)) {
          leaks.push(`${table}.${col}`);
        }
      }
    }
    expect(leaks).toEqual([]);
  });

  it('không bảng nào khai báo cột sinh của PostgreSQL', () => {
    // *_day_local are recomputed by PostgreSQL on write; a client sending one
    // back would be rejected by the database.
    const generated: string[] = [];
    for (const table of Object.keys(mySchema.tables)) {
      for (const col of columnsOf(table)) {
        if (col.endsWith('_day_local')) {
          generated.push(`${table}.${col}`);
        }
      }
    }
    expect(generated).toEqual([]);
  });

  it('không khai báo lại cột nội bộ của WatermelonDB', () => {
    // Declaring _status or _changed causes a schema conflict at runtime.
    for (const table of Object.keys(mySchema.tables)) {
      const cols = columnsOf(table);
      expect(cols).not.toContain('_status');
      expect(cols).not.toContain('_changed');
      expect(cols).not.toContain('id');
    }
  });

  it('phiên bản schema khớp hợp đồng', () => {
    expect(SCHEMA_VERSION).toBe(contract.schema_version);
  });
});

describe('Kiểu cột', () => {
  it('chỉ dùng ba kiểu WatermelonDB hỗ trợ', () => {
    const allowed = new Set(['string', 'number', 'boolean']);
    for (const table of Object.keys(mySchema.tables)) {
      const {columns} = mySchema.tables[table]!;
      for (const [name, col] of Object.entries(columns)) {
        expect(allowed.has(col.type)).toBe(true);
        expect(`${table}.${name}:${col.type}`).toBeTruthy();
      }
    }
  });

  it('ngày nghiệp vụ là number (epoch ms), không phải string', () => {
    // Exact parity with the backend's BIGINT columns — no timezone
    // conversion at the sync boundary (§7.2).
    const dateColumns = [
      ['seasons', 'start_date'],
      ['diary_entries', 'entry_date'],
      ['stock_transactions', 'txn_date'],
      ['expenses', 'expense_date'],
      ['revenues', 'revenue_date'],
      ['seasons', 'created_at'],
      ['seasons', 'updated_at'],
    ] as const;

    for (const [table, column] of dateColumns) {
      expect(mySchema.tables[table]!.columns[column]!.type).toBe('number');
    }
  });

  it('tiền và số lượng là number', () => {
    const numeric = [
      ['supplies', 'unit_cost'],
      ['supplies', 'low_stock_threshold'],
      ['stock_transactions', 'quantity'],
      ['stock_transactions', 'total_cost'],
      ['expenses', 'amount'],
      ['revenues', 'amount'],
    ] as const;

    for (const [table, column] of numeric) {
      expect(mySchema.tables[table]!.columns[column]!.type).toBe('number');
    }
  });

  it('khoá ngoại đều được đánh index', () => {
    // The offline list screens filter on these constantly.
    const foreignKeys = [
      ['diary_entries', 'season_id'],
      ['stock_transactions', 'supply_id'],
      ['stock_transactions', 'season_id'],
      ['stock_transactions', 'diary_entry_id'],
      ['expenses', 'season_id'],
      ['expenses', 'stock_transaction_id'],
      ['revenues', 'season_id'],
    ] as const;

    for (const [table, column] of foreignKeys) {
      expect(mySchema.tables[table]!.columns[column]!.isIndexed).toBe(true);
    }
  });
});
