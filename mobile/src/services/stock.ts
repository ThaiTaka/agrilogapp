/**
 * Inventory ledger — the client half (Issues #24, #26).
 *
 * Mirrors backend/app/services/supply_service.py. The two implementations
 * must produce identical numbers for identical input: any asymmetry surfaces
 * as data drift after a sync, which is the hardest class of bug this project
 * can ship because it only appears once two devices disagree.
 *
 * The central rule, same as the server:
 *
 *     on-hand is NEVER stored. It is always Σin + Σadjust − Σout
 *     over the live ledger.
 *
 * A cached counter decremented independently by two offline devices produces
 * a number that is simply wrong after sync, with no way to detect it (D1).
 */

import {Database, Q} from '@nozbe/watermelondb';

import {TxnType} from '../db/enums';
import type {StockTransaction, Supply} from '../db/models';
import {lineTotal, quantizeMoney, quantizeQuantity} from '../utils/numeric';

// ─── Derived stock levels ───────────────────────────────────────────────────

/**
 * On-hand quantity for many supplies, from ONE query.
 *
 * Batched deliberately: computing this per row would turn a 40-item inventory
 * screen into 41 round-trips to SQLite, which is exactly what makes an app
 * feel broken on a low-end phone.
 */
export async function stockLevels(
  database: Database,
  supplyIds?: string[],
): Promise<Map<string, number>> {
  const conditions = [Q.where('txn_type', Q.notEq(''))];
  if (supplyIds) {
    if (supplyIds.length === 0) {
      return new Map();
    }
    conditions.push(Q.where('supply_id', Q.oneOf(supplyIds)));
  }

  const rows = await database
    .get<StockTransaction>('stock_transactions')
    .query(...conditions)
    .fetch();

  const levels = new Map<string, number>();
  for (const txn of rows) {
    const delta = txn.txnType === TxnType.OUT ? -txn.quantity : txn.quantity;
    levels.set(txn.supplyId, (levels.get(txn.supplyId) ?? 0) + delta);
  }

  // Quantise once at the end, not per addition — rounding each step would
  // drift, and the server sums in Decimal then rounds once too.
  for (const [id, total] of levels) {
    levels.set(id, quantizeQuantity(total));
  }
  return levels;
}

export async function stockLevel(database: Database, supplyId: string): Promise<number> {
  return (await stockLevels(database, [supplyId])).get(supplyId) ?? 0;
}

export function isLowStock(supply: Supply, onHand: number): boolean {
  return supply.lowStockThreshold > 0 && onHand <= supply.lowStockThreshold;
}

// ─── Movements ──────────────────────────────────────────────────────────────

export interface MovementInput {
  supplyId: string;
  quantity: number;
  unitCost?: number;
  seasonId?: string | null;
  txnDate?: Date;
  note?: string | null;
}

async function appendMovement(
  database: Database,
  input: MovementInput,
  txnType: TxnType,
  diaryEntryId: string | null,
): Promise<StockTransaction> {
  const supply = await database.get<Supply>('supplies').find(input.supplyId);
  const quantity = quantizeQuantity(input.quantity);
  // Snapshot, never a live read at report time: fertiliser bought in March at
  // 12,000đ/kg and used in September stays costed at what it actually cost.
  const unitCost = quantizeMoney(input.unitCost ?? supply.unitCost);

  return database.get<StockTransaction>('stock_transactions').create(txn => {
    txn.supplyId = input.supplyId;
    txn.seasonId = input.seasonId ?? null;
    txn.diaryEntryId = diaryEntryId;
    txn.txnType = txnType;
    txn.quantity = quantity;
    txn.unitCost = unitCost;
    txn.totalCost = lineTotal(quantity, unitCost);
    txn.txnDate = input.txnDate ?? new Date();
    txn.note = input.note ?? null;
  });
}

/** Nhập kho. */
export async function recordStockIn(
  database: Database,
  input: MovementInput,
): Promise<StockTransaction> {
  return database.write(() => appendMovement(database, input, TxnType.IN, null));
}

/**
 * Xuất kho, recorded directly from the inventory screen.
 *
 * Generates NO expense (invariant I7): this movement is a stock-take or a
 * transfer, and the money left the household when the supply was bought.
 * Booking a cost again here would double-count.
 *
 * Taking out more than is on hand is allowed and produces a negative balance
 * (I2). Blocking it would force a farmer who forgot to log a purchase to
 * abandon the usage entry, and a missing log is worse than a number they can
 * correct later.
 */
export async function recordStockOut(
  database: Database,
  input: MovementInput,
): Promise<StockTransaction> {
  return database.write(() => appendMovement(database, input, TxnType.OUT, null));
}

/**
 * Kiểm kê — the farmer counts what is physically there and the app records
 * the delta.
 *
 * Asking for a delta instead would make them do arithmetic against a number
 * they do not trust, which is the reason they are counting in the first
 * place.
 *
 * A count matching the ledger writes NOTHING. A no-op row would bump
 * updated_at and manufacture a phantom last-write-wins conflict against
 * another device editing the same supply.
 */
export async function recordStockTake(
  database: Database,
  supplyId: string,
  countedQuantity: number,
  note?: string,
): Promise<{transaction: StockTransaction | null; delta: number}> {
  const current = await stockLevel(database, supplyId);
  const counted = quantizeQuantity(countedQuantity);
  const delta = quantizeQuantity(counted - current);

  if (delta === 0) {
    return {transaction: null, delta: 0};
  }

  const transaction = await database.write(() =>
    database.get<StockTransaction>('stock_transactions').create(txn => {
      txn.supplyId = supplyId;
      txn.seasonId = null;
      txn.diaryEntryId = null;
      txn.txnType = TxnType.ADJUST;
      txn.quantity = delta; // signed
      txn.unitCost = 0;
      txn.totalCost = 0;
      txn.txnDate = new Date();
      txn.note = note ?? `Kiểm kê: ${current} → ${counted}`;
    }),
  );

  return {transaction, delta};
}

/**
 * Huỷ một giao dịch kho, returning its effect to the derived balance.
 *
 * Refused for movements owned by a diary entry: those are reconciled by
 * editing the entry (see diary.ts), and voiding one here would leave the
 * entry claiming a consumption that no longer exists in the ledger.
 */
export async function voidMovement(database: Database, txnId: string): Promise<void> {
  const txn = await database.get<StockTransaction>('stock_transactions').find(txnId);

  if (txn.diaryEntryId !== null) {
    throw new Error(
      'Giao dịch này được sinh từ nhật ký canh tác. ' +
        'Hãy sửa hoặc xoá nhật ký tương ứng để hoàn kho.',
    );
  }

  // markAsDeleted, not destroyPermanently: the deletion has to reach every
  // other device through sync, and a hard local delete is invisible to them.
  await database.write(() => txn.markAsDeleted());
}
