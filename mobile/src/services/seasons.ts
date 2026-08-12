/**
 * Season CRUD against the local database (Issue #20).
 *
 * Every function writes to WatermelonDB and returns. Nothing here touches the
 * network — the sync engine reconciles later. If a screen ever needs to wait
 * on a request to show a season, the design has gone wrong.
 */

import {Database, Q} from '@nozbe/watermelondb';

import {SeasonStatus} from '../db/enums';
import type {DiaryEntry, Expense, Revenue, Season, StockTransaction} from '../db/models';
import {quantizeMoney, quantizeQuantity} from '../utils/numeric';

export interface SeasonInput {
  name: string;
  cropType: string;
  areaSize?: number | null;
  areaUnit?: string;
  startDate: Date;
  endDate?: Date | null;
  status?: SeasonStatus;
  note?: string | null;
}

export class ValidationError extends Error {}

/**
 * Validated here as well as by the server's CHECK constraint and Pydantic
 * schema. Three layers, because a bad range silently breaks every report that
 * filters by the season window, and a silent report bug costs far more to
 * find than a loud validation error.
 */
export function validateSeason(input: SeasonInput): void {
  if (!input.name.trim()) {
    throw new ValidationError('Tên mùa vụ không được để trống.');
  }
  if (input.name.trim().length > 120) {
    throw new ValidationError('Tên mùa vụ tối đa 120 ký tự.');
  }
  if (!input.cropType.trim()) {
    throw new ValidationError('Loại cây trồng không được để trống.');
  }
  if (input.areaSize !== null && input.areaSize !== undefined && input.areaSize < 0) {
    throw new ValidationError('Diện tích không được âm.');
  }
  if (input.endDate && input.endDate.getTime() < input.startDate.getTime()) {
    throw new ValidationError('Ngày kết thúc không được trước ngày bắt đầu.');
  }
}

export function observeSeasons(database: Database, status?: SeasonStatus) {
  const conditions = status ? [Q.where('status', status)] : [];
  return database
    .get<Season>('seasons')
    .query(...conditions, Q.sortBy('start_date', Q.desc))
    .observeWithColumns(['name', 'crop_type', 'status', 'start_date', 'end_date']);
}

export async function createSeason(
  database: Database,
  input: SeasonInput,
): Promise<Season> {
  validateSeason(input);

  return database.write(() =>
    database.get<Season>('seasons').create(s => {
      s.name = input.name.trim();
      s.cropType = input.cropType.trim();
      s.areaSize =
        input.areaSize === null || input.areaSize === undefined
          ? null
          : quantizeQuantity(input.areaSize);
      s.areaUnit = input.areaUnit ?? 'sao';
      s.startDate = input.startDate;
      s.endDate = input.endDate ?? null;
      s.status = input.status ?? SeasonStatus.ACTIVE;
      s.note = input.note ?? null;
    }),
  );
}

export async function updateSeason(
  database: Database,
  seasonId: string,
  patch: Partial<SeasonInput>,
): Promise<Season> {
  const season = await database.get<Season>('seasons').find(seasonId);

  // Validate against the MERGED record, not the patch alone — changing only
  // endDate must still be checked against the stored startDate.
  validateSeason({
    name: patch.name ?? season.name,
    cropType: patch.cropType ?? season.cropType,
    areaSize: patch.areaSize !== undefined ? patch.areaSize : season.areaSize,
    startDate: patch.startDate ?? season.startDate,
    endDate: patch.endDate !== undefined ? patch.endDate : season.endDate,
  });

  return database.write(() =>
    season.update(s => {
      if (patch.name !== undefined) {
        s.name = patch.name.trim();
      }
      if (patch.cropType !== undefined) {
        s.cropType = patch.cropType.trim();
      }
      if (patch.areaSize !== undefined) {
        s.areaSize = patch.areaSize === null ? null : quantizeQuantity(patch.areaSize);
      }
      if (patch.areaUnit !== undefined) {
        s.areaUnit = patch.areaUnit;
      }
      if (patch.startDate !== undefined) {
        s.startDate = patch.startDate;
      }
      if (patch.endDate !== undefined) {
        s.endDate = patch.endDate;
      }
      if (patch.status !== undefined) {
        s.status = patch.status;
      }
      if (patch.note !== undefined) {
        s.note = patch.note;
      }
    }),
  );
}

export interface SeasonDeleteResult {
  diaryEntries: number;
  expenses: number;
  revenues: number;
  transactionsReversed: number;
  transactionsUnlinked: number;
}

/**
 * Xoá mùa vụ và mọi dữ liệu con.
 *
 * The cascade is deliberately asymmetric, mirroring the server (§8.4):
 *
 *   diary entries, expenses, revenues  → tombstoned
 *   movements FROM a diary entry       → tombstoned, so stock returns (I3)
 *   standalone purchases               → DE-ALLOCATED, not deleted
 *
 * A purchase booked against the season really happened, and the fertiliser is
 * still physically in the shed. Deleting it would erase a real transaction
 * and silently change the on-hand quantity. The ledger is append-only (D1);
 * a season being deleted is not a reason to rewrite it.
 */
export async function deleteSeason(
  database: Database,
  seasonId: string,
): Promise<SeasonDeleteResult> {
  return database.write(async () => {
    const season = await database.get<Season>('seasons').find(seasonId);

    const entries = await database
      .get<DiaryEntry>('diary_entries')
      .query(Q.where('season_id', seasonId))
      .fetch();
    const expenses = await database
      .get<Expense>('expenses')
      .query(Q.where('season_id', seasonId))
      .fetch();
    const revenues = await database
      .get<Revenue>('revenues')
      .query(Q.where('season_id', seasonId))
      .fetch();
    const movements = await database
      .get<StockTransaction>('stock_transactions')
      .query(Q.where('season_id', seasonId))
      .fetch();

    let reversed = 0;
    let unlinked = 0;
    for (const txn of movements) {
      if (txn.diaryEntryId !== null) {
        await txn.markAsDeleted();
        reversed += 1;
      } else {
        await txn.update(t => (t.seasonId = null));
        unlinked += 1;
      }
    }

    for (const row of [...expenses, ...revenues, ...entries]) {
      await row.markAsDeleted();
    }
    await season.markAsDeleted();

    return {
      diaryEntries: entries.length,
      expenses: expenses.length,
      revenues: revenues.length,
      transactionsReversed: reversed,
      transactionsUnlinked: unlinked,
    };
  });
}

// ─── Tổng kết tài chính ─────────────────────────────────────────────────────

export interface SeasonTotals {
  totalCost: number;
  totalRevenue: number;
  profit: number;
  marginPct: number | null;
}

/**
 * Computed, never stored (invariant I10).
 *
 * Supply consumption is already present as `diary_auto` expenses, so this
 * includes it with no separate step and double-counting is structurally
 * impossible (I9).
 */
export async function seasonTotals(
  database: Database,
  seasonId: string,
): Promise<SeasonTotals> {
  const [expenses, revenues] = await Promise.all([
    database.get<Expense>('expenses').query(Q.where('season_id', seasonId)).fetch(),
    database.get<Revenue>('revenues').query(Q.where('season_id', seasonId)).fetch(),
  ]);

  const totalCost = quantizeMoney(expenses.reduce((s, e) => s + e.amount, 0));
  const totalRevenue = quantizeMoney(revenues.reduce((s, r) => s + r.amount, 0));
  const profit = quantizeMoney(totalRevenue - totalCost);

  return {
    totalCost,
    totalRevenue,
    profit,
    // null rather than 0 when there is no revenue: "no margin computed" and
    // "zero margin" are different facts.
    marginPct: totalRevenue > 0 ? Math.round((profit / totalRevenue) * 1000) / 10 : null,
  };
}
