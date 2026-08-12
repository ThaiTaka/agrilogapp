/**
 * Diary entries with automatic stock restore and expense generation.
 *
 * Implements Issue #26 (hoàn kho offline) and the mobile half of #29
 * (auto expense). Mirrors backend/app/services/diary_service.py — the two
 * must produce identical numbers, because a farmer who edits an entry in
 * airplane mode and a farmer who edits the same entry online must end up with
 * the same inventory and the same costs.
 *
 * The invariants (Data_Requirements_Database.md §9), tested in
 * __tests__/diary.test.ts against a real WatermelonDB instance:
 *
 *   I3  create → edit → delete returns on-hand to EXACTLY its prior value
 *   I4  the restore is idempotent
 *   I6  exactly one expense per supply-consuming movement
 *   I7  a bare stock-out generates no expense
 *
 * Everything here runs inside a single `database.write()` block, so the app
 * crashing mid-restore cannot leave a half-restored inventory (I5).
 */

import {Database, Q} from '@nozbe/watermelondb';

import {ExpenseCategory, ExpenseSource, TxnType, type WorkType} from '../db/enums';
import type {DiaryEntry, Expense, StockTransaction, Supply} from '../db/models';
import {lineTotal, quantizeMoney, quantizeQuantity} from '../utils/numeric';

export interface SupplyUsageInput {
  supplyId: string;
  quantity: number;
  unitCost?: number;
  note?: string | null;
}

export interface DiaryEntryInput {
  seasonId: string;
  workType: WorkType;
  entryDate?: Date;
  title?: string | null;
  note?: string | null;
  weather?: string | null;
  laborHours?: number | null;
  supplyUsages?: SupplyUsageInput[];
}

export type DiaryEntryPatch = Partial<Omit<DiaryEntryInput, 'supplyUsages'>> & {
  /**
   * `undefined` leaves consumption untouched; `[]` reverses all of it.
   *
   * The two are deliberately different. Collapsing them would make "I only
   * fixed a typo in the note" silently wipe the farmer's fertiliser record.
   */
  supplyUsages?: SupplyUsageInput[];
};

// ─── Internal helpers (must be called inside a writer) ──────────────────────

async function liveUsages(
  database: Database,
  entryId: string,
): Promise<StockTransaction[]> {
  return database
    .get<StockTransaction>('stock_transactions')
    .query(Q.where('diary_entry_id', entryId))
    .fetch();
}

async function expenseFor(
  database: Database,
  txnId: string,
): Promise<Expense | null> {
  const rows = await database
    .get<Expense>('expenses')
    .query(Q.where('stock_transaction_id', txnId))
    .fetch();
  return rows[0] ?? null;
}

/**
 * Create or update the `diary_auto` expense mirroring a stock movement.
 *
 * Idempotent (I4): called twice for the same movement it converges on one
 * row, because it looks the expense up by stock_transaction_id before
 * deciding to insert. The server enforces this structurally with a unique
 * index; the client relies on that as the backstop rather than trying to
 * police concurrency locally.
 */
async function syncAutoExpense(
  database: Database,
  txn: StockTransaction,
  seasonId: string,
): Promise<void> {
  const existing = await expenseFor(database, txn.id);

  if (existing) {
    await existing.update(e => {
      e.amount = txn.totalCost;
      e.expenseDate = txn.txnDate;
      e.seasonId = seasonId;
      e.category = ExpenseCategory.SUPPLY;
      e.source = ExpenseSource.DIARY_AUTO;
    });
    return;
  }

  await database.get<Expense>('expenses').create(e => {
    e.seasonId = seasonId;
    e.stockTransactionId = txn.id;
    e.category = ExpenseCategory.SUPPLY;
    e.amount = txn.totalCost;
    e.expenseDate = txn.txnDate;
    e.description = null;
    e.source = ExpenseSource.DIARY_AUTO;
  });
}

async function voidAutoExpense(database: Database, txnId: string): Promise<void> {
  const expense = await expenseFor(database, txnId);
  if (expense) {
    await expense.markAsDeleted();
  }
}

/**
 * Reconcile an entry's ledger rows against the submitted usage list.
 *
 * Matched by supplyId, which is why duplicate supplies in one entry are
 * rejected at the edge — otherwise "which line changed?" has no answer.
 *
 * Four cases, and the third matters more than it looks:
 *
 *   added     → new stock-out + its auto expense
 *   changed   → update quantity and total, expense follows
 *   SAME      → write NOTHING
 *   removed   → tombstone the movement and its expense; stock returns
 *
 * The no-op case is not an optimisation. Touching a row bumps updated_at, and
 * updated_at drives last-write-wins. Rewriting an unchanged row manufactures
 * a conflict against another device that legitimately edited it, and that
 * device's edit loses.
 */
async function applyUsages(
  database: Database,
  entry: DiaryEntry,
  usages: SupplyUsageInput[],
): Promise<void> {
  assertNoDuplicateSupplies(usages);

  const existing = new Map<string, StockTransaction>();
  for (const txn of await liveUsages(database, entry.id)) {
    existing.set(txn.supplyId, txn);
  }
  const submitted = new Map(usages.map(u => [u.supplyId, u]));

  // ── removed ──
  for (const [supplyId, txn] of existing) {
    if (submitted.has(supplyId)) {
      continue;
    }
    await voidAutoExpense(database, txn.id);
    await txn.markAsDeleted();
  }

  // ── added / changed / unchanged ──
  for (const [supplyId, usage] of submitted) {
    const supply = await database.get<Supply>('supplies').find(supplyId);
    const quantity = quantizeQuantity(usage.quantity);
    const unitCost = quantizeMoney(usage.unitCost ?? supply.unitCost);
    const total = lineTotal(quantity, unitCost);

    let txn = existing.get(supplyId);

    if (!txn) {
      txn = await database.get<StockTransaction>('stock_transactions').create(t => {
        t.supplyId = supplyId;
        t.seasonId = entry.seasonId;
        t.diaryEntryId = entry.id;
        t.txnType = TxnType.OUT;
        t.quantity = quantity;
        t.unitCost = unitCost;
        t.totalCost = total;
        t.txnDate = entry.entryDate;
        t.note = usage.note ?? null;
      });
    } else if (
      txn.quantity !== quantity ||
      txn.unitCost !== unitCost ||
      txn.txnDate.getTime() !== entry.entryDate.getTime() ||
      txn.seasonId !== entry.seasonId ||
      txn.note !== (usage.note ?? null)
    ) {
      const target = txn;
      await target.update(t => {
        t.quantity = quantity;
        t.unitCost = unitCost;
        t.totalCost = total;
        t.txnDate = entry.entryDate;
        t.seasonId = entry.seasonId;
        t.note = usage.note ?? null;
      });
    }
    // else: identical → deliberately no write

    await syncAutoExpense(database, txn, entry.seasonId);
  }
}

export function assertNoDuplicateSupplies(usages: SupplyUsageInput[]): void {
  const seen = new Set<string>();
  for (const usage of usages) {
    if (seen.has(usage.supplyId)) {
      throw new Error(
        'Mỗi vật tư chỉ được khai báo một dòng trong cùng một nhật ký. ' +
          'Hãy cộng gộp số lượng lại.',
      );
    }
    seen.add(usage.supplyId);
  }
}

// ─── Public API ─────────────────────────────────────────────────────────────

/**
 * Ghi nhật ký, optionally consuming supplies.
 *
 * One writer block does three things: writes the entry, appends a stock-out
 * per supply, and generates the matching expense. The farmer enters the
 * fertiliser once.
 */
export async function createDiaryEntry(
  database: Database,
  input: DiaryEntryInput,
): Promise<DiaryEntry> {
  assertNoDuplicateSupplies(input.supplyUsages ?? []);

  return database.write(async () => {
    const entry = await database.get<DiaryEntry>('diary_entries').create(e => {
      e.seasonId = input.seasonId;
      e.workType = input.workType;
      e.entryDate = input.entryDate ?? new Date();
      e.title = input.title ?? null;
      e.note = input.note ?? null;
      e.weather = input.weather ?? null;
      e.laborHours = input.laborHours ?? null;
    });

    if (input.supplyUsages?.length) {
      await applyUsages(database, entry, input.supplyUsages);
    }
    return entry;
  });
}

/** Sửa nhật ký — adjusts inventory automatically (hoàn kho). */
export async function updateDiaryEntry(
  database: Database,
  entryId: string,
  patch: DiaryEntryPatch,
): Promise<DiaryEntry> {
  if (patch.supplyUsages) {
    assertNoDuplicateSupplies(patch.supplyUsages);
  }

  return database.write(async () => {
    const entry = await database.get<DiaryEntry>('diary_entries').find(entryId);
    const dateChanged =
      patch.entryDate !== undefined &&
      patch.entryDate.getTime() !== entry.entryDate.getTime();
    const seasonChanged = patch.seasonId !== undefined && patch.seasonId !== entry.seasonId;

    await entry.update(e => {
      if (patch.seasonId !== undefined) {
        e.seasonId = patch.seasonId;
      }
      if (patch.workType !== undefined) {
        e.workType = patch.workType;
      }
      if (patch.entryDate !== undefined) {
        e.entryDate = patch.entryDate;
      }
      if (patch.title !== undefined) {
        e.title = patch.title;
      }
      if (patch.note !== undefined) {
        e.note = patch.note;
      }
      if (patch.weather !== undefined) {
        e.weather = patch.weather;
      }
      if (patch.laborHours !== undefined) {
        e.laborHours = patch.laborHours;
      }
    });

    if (patch.supplyUsages !== undefined) {
      await applyUsages(database, entry, patch.supplyUsages);
    } else if (dateChanged || seasonChanged) {
      // The entry moved, so its child movements must move with it — a
      // consumption dated differently from the work that caused it lands in
      // the wrong report bucket and the wrong season's cost total.
      const current = await liveUsages(database, entry.id);
      await applyUsages(
        database,
        entry,
        current.map(t => ({
          supplyId: t.supplyId,
          quantity: t.quantity,
          unitCost: t.unitCost,
          note: t.note,
        })),
      );
    }

    return entry;
  });
}

export interface DeleteResult {
  transactionsReversed: number;
  expensesRemoved: number;
  /** supplyId → quantity returned to inventory */
  quantityRestored: Map<string, number>;
}

/**
 * Xoá nhật ký và hoàn kho toàn bộ.
 *
 * This is hoàn kho in its simplest form: the work did not happen, so the
 * fertiliser was not used, so it goes back on the shelf.
 */
export async function deleteDiaryEntry(
  database: Database,
  entryId: string,
): Promise<DeleteResult> {
  return database.write(async () => {
    const entry = await database.get<DiaryEntry>('diary_entries').find(entryId);
    const usages = await liveUsages(database, entryId);

    const quantityRestored = new Map<string, number>();
    let expensesRemoved = 0;

    for (const txn of usages) {
      quantityRestored.set(
        txn.supplyId,
        quantizeQuantity((quantityRestored.get(txn.supplyId) ?? 0) + txn.quantity),
      );
      const expense = await expenseFor(database, txn.id);
      if (expense) {
        await expense.markAsDeleted();
        expensesRemoved += 1;
      }
      await txn.markAsDeleted();
    }

    await entry.markAsDeleted();

    return {
      transactionsReversed: usages.length,
      expensesRemoved,
      quantityRestored,
    };
  });
}

/** Σ total_cost of an entry's consumptions — equals its auto-generated expenses. */
export async function entrySupplyCost(
  database: Database,
  entryId: string,
): Promise<number> {
  const usages = await liveUsages(database, entryId);
  return quantizeMoney(usages.reduce((sum, t) => sum + t.totalCost, 0));
}
