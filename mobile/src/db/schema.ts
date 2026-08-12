/**
 * WatermelonDB schema — mirrors the PostgreSQL schema table-for-table.
 *
 * Implements Issue #8. The authority is Data_Requirements_Database.md §5;
 * this file must not diverge from it, because a field-name mismatch between
 * the two schemas is the single highest-probability cause of a silent sync
 * bug in this project.
 *
 * DELIBERATELY ABSENT from every table:
 *
 *   household_id       The client already knows its household from the JWT and
 *                      every row it can see belongs to it. Sending it would add
 *                      a column carrying zero information and create one more
 *                      chance to diverge. The server re-attaches it on push
 *                      from the token — which also means a client cannot write
 *                      into another household by forging a field that is never
 *                      read.
 *   server_updated_at  Server clock, the pull cursor. Never leaves the server.
 *   deleted_at         Server-side tombstone. WatermelonDB has its own delete
 *                      bookkeeping.
 *   last_device_id     Server-side audit.
 *   name_key           Derived from `name` by the server (casefold + NFC).
 *   *_day_local        PostgreSQL generated columns. Recomputed on write; a
 *                      client sending one would be rejected.
 *   _status, _changed  Added by WatermelonDB itself. Declaring them here
 *                      causes a schema conflict.
 *
 * See Data_Requirements_Database.md §6.2 and §6.3.
 */

import {appSchema, tableSchema} from '@nozbe/watermelondb';

/**
 * Bump on EVERY change to this file, together with a matching entry in
 * migrations.ts and an Alembic migration on the backend. The three move
 * together or sync breaks.
 */
export const SCHEMA_VERSION = 1;

export const mySchema = appSchema({
  version: SCHEMA_VERSION,
  tables: [
    tableSchema({
      name: 'seasons',
      columns: [
        {name: 'name', type: 'string'},
        {name: 'crop_type', type: 'string'},
        {name: 'area_size', type: 'number', isOptional: true},
        {name: 'area_unit', type: 'string'},
        {name: 'start_date', type: 'number', isIndexed: true},
        {name: 'end_date', type: 'number', isOptional: true},
        {name: 'status', type: 'string', isIndexed: true},
        {name: 'note', type: 'string', isOptional: true},
        {name: 'created_at', type: 'number'},
        {name: 'updated_at', type: 'number'},
      ],
    }),

    tableSchema({
      name: 'supplies',
      columns: [
        {name: 'name', type: 'string'},
        {name: 'category', type: 'string', isIndexed: true},
        {name: 'unit', type: 'string'},
        // VND per unit. Money is a whole number of đồng, far below float64's
        // exact-integer ceiling, so this is lossless (§7.1).
        {name: 'unit_cost', type: 'number'},
        {name: 'low_stock_threshold', type: 'number'},
        {name: 'is_archived', type: 'boolean', isIndexed: true},
        {name: 'note', type: 'string', isOptional: true},
        {name: 'created_at', type: 'number'},
        {name: 'updated_at', type: 'number'},
      ],
    }),

    tableSchema({
      name: 'diary_entries',
      columns: [
        {name: 'season_id', type: 'string', isIndexed: true},
        {name: 'work_type', type: 'string', isIndexed: true},
        {name: 'entry_date', type: 'number', isIndexed: true},
        {name: 'title', type: 'string', isOptional: true},
        {name: 'note', type: 'string', isOptional: true},
        {name: 'weather', type: 'string', isOptional: true},
        {name: 'labor_hours', type: 'number', isOptional: true},
        {name: 'created_at', type: 'number'},
        {name: 'updated_at', type: 'number'},
      ],
    }),

    tableSchema({
      name: 'stock_transactions',
      columns: [
        {name: 'supply_id', type: 'string', isIndexed: true},
        {name: 'season_id', type: 'string', isOptional: true, isIndexed: true},
        // Set ⟺ the movement came from a diary entry. This is what unifies
        // "consumption logged from a diary entry" and "stock-out from the
        // inventory screen" into ONE ledger, and what makes hoàn kho a
        // bounded operation: reconcile the children of one parent.
        {name: 'diary_entry_id', type: 'string', isOptional: true, isIndexed: true},
        {name: 'txn_type', type: 'string', isIndexed: true},
        // Always positive for in/out; direction comes from txn_type.
        // `adjust` carries a signed delta.
        {name: 'quantity', type: 'number'},
        // Snapshot of the supply's price at movement time, never a live join.
        // Fertiliser bought in March at 12,000đ/kg and used in September must
        // stay costed at what it actually cost.
        {name: 'unit_cost', type: 'number'},
        {name: 'total_cost', type: 'number'},
        {name: 'txn_date', type: 'number', isIndexed: true},
        {name: 'note', type: 'string', isOptional: true},
        {name: 'created_at', type: 'number'},
        {name: 'updated_at', type: 'number'},
      ],
    }),

    tableSchema({
      name: 'expenses',
      columns: [
        {name: 'season_id', type: 'string', isIndexed: true},
        // Set ⟺ source = 'diary_auto'. The server enforces one expense per
        // movement with a unique index; the client relies on that rather than
        // trying to police it locally.
        {name: 'stock_transaction_id', type: 'string', isOptional: true, isIndexed: true},
        {name: 'category', type: 'string', isIndexed: true},
        {name: 'amount', type: 'number'},
        {name: 'expense_date', type: 'number', isIndexed: true},
        {name: 'description', type: 'string', isOptional: true},
        {name: 'source', type: 'string', isIndexed: true},
        {name: 'created_at', type: 'number'},
        {name: 'updated_at', type: 'number'},
      ],
    }),

    tableSchema({
      name: 'revenues',
      columns: [
        {name: 'season_id', type: 'string', isIndexed: true},
        {name: 'quantity', type: 'number', isOptional: true},
        {name: 'unit', type: 'string', isOptional: true},
        {name: 'unit_price', type: 'number', isOptional: true},
        // Authoritative even when quantity × unit_price is also present. Real
        // sales get rounded down, discounted for moisture, or partly paid.
        {name: 'amount', type: 'number'},
        {name: 'revenue_date', type: 'number', isIndexed: true},
        {name: 'buyer', type: 'string', isOptional: true},
        {name: 'description', type: 'string', isOptional: true},
        {name: 'created_at', type: 'number'},
        {name: 'updated_at', type: 'number'},
      ],
    }),
  ],
});

/**
 * Tables that cross the sync boundary, in dependency order.
 *
 * Must match SYNC_TABLE_ORDER in backend/app/db/base.py exactly. Both sides
 * apply upserts in this order and deletes in reverse, so a batch never
 * inserts a child before its parent.
 */
export const SYNC_TABLES = [
  'seasons',
  'supplies',
  'diary_entries',
  'stock_transactions',
  'expenses',
  'revenues',
] as const;

export type SyncTable = (typeof SYNC_TABLES)[number];
