/**
 * Report aggregation — the client half (Issues #43–#47).
 *
 * Mirrors backend/app/services/report_service.py. Both sides must produce
 * identical numbers for identical data: docs/reports_golden.json is asserted
 * by the backend pytest suite AND by this module's Jest suite, which is what
 * makes "the chart shows the same number offline and online" a tested
 * property rather than a hope (§11.4).
 *
 * All three charts read only local WatermelonDB, so they render in airplane
 * mode (Issue #47). The backend endpoints exist as a cross-check and for a
 * future web view, not as the source.
 */

import {Database, Q} from '@nozbe/watermelondb';

import {
  EXPENSE_CATEGORY_LABELS,
  SUPPLY_CATEGORY_LABELS,
  SeasonStatus,
  SupplyCategory,
  TxnType,
} from '../db/enums';
import type {Expense, Revenue, Season, StockTransaction, Supply} from '../db/models';
import {
  localDayIndex,
  localDayKey,
  localMonthKey,
  localWeekKey,
  MS_PER_DAY,
} from '../utils/date';
import {quantizeMoney, quantizeQuantity} from '../utils/numeric';

export type Granularity = 'day' | 'week' | 'month';
export type GroupBy = 'category' | 'supply';

/**
 * A guard, not a business rule: a season with a corrupt start date could
 * otherwise ask for millions of empty buckets and hang the UI thread.
 */
const MAX_DENSE_DAYS = 2000;

function bucketKey(dayIndex: number, granularity: Granularity): string {
  const ms = dayIndex * MS_PER_DAY;
  if (granularity === 'day') {
    return localDayKey(ms);
  }
  if (granularity === 'week') {
    return localWeekKey(ms);
  }
  return localMonthKey(ms);
}

/**
 * Every bucket in the range, in order, including empty ones.
 *
 * Walks day by day and collects distinct keys rather than stepping in weeks
 * or months. Month lengths and ISO week boundaries are exactly the arithmetic
 * that goes wrong when done cleverly, and a few hundred iterations costs
 * nothing.
 */
function denseKeys(firstDay: number, lastDay: number, granularity: Granularity): string[] {
  if (lastDay < firstDay) {
    return [];
  }
  const span = Math.min(lastDay - firstDay, MAX_DENSE_DAYS);
  const keys: string[] = [];
  const seen = new Set<string>();

  for (let i = 0; i <= span; i++) {
    const key = bucketKey(firstDay + i, granularity);
    if (!seen.has(key)) {
      seen.add(key);
      keys.push(key);
    }
  }
  return keys;
}

// ═══════════════════════════════════════════════════════════════════════════
//  Biểu đồ 1 — Thu chi theo thời gian
// ═══════════════════════════════════════════════════════════════════════════

export interface IncomeExpenseBucket {
  period: string;
  revenue: number;
  expense: number;
  profit: number;
}

export interface IncomeExpenseReport {
  seasonId: string;
  seasonName: string;
  granularity: Granularity;
  buckets: IncomeExpenseBucket[];
  totals: {revenue: number; expense: number; profit: number};
}

export async function incomeExpenseReport(
  database: Database,
  seasonId: string,
  granularity: Granularity = 'month',
): Promise<IncomeExpenseReport> {
  const season = await database.get<Season>('seasons').find(seasonId);
  const [expenses, revenues] = await Promise.all([
    database.get<Expense>('expenses').query(Q.where('season_id', seasonId)).fetch(),
    database.get<Revenue>('revenues').query(Q.where('season_id', seasonId)).fetch(),
  ]);

  const expenseByBucket = new Map<string, number>();
  const revenueByBucket = new Map<string, number>();
  const observedDays: number[] = [];

  for (const e of expenses) {
    const day = localDayIndex(e.expenseDate.getTime());
    observedDays.push(day);
    const key = bucketKey(day, granularity);
    expenseByBucket.set(key, (expenseByBucket.get(key) ?? 0) + e.amount);
  }
  for (const r of revenues) {
    const day = localDayIndex(r.revenueDate.getTime());
    observedDays.push(day);
    const key = bucketKey(day, granularity);
    revenueByBucket.set(key, (revenueByBucket.get(key) ?? 0) + r.amount);
  }

  // The range is the SEASON's window, not the range of recorded activity. A
  // season that starts in December with its first cost in February should
  // show two empty months first — that gap is information.
  let firstDay = localDayIndex(season.startDate.getTime());
  let lastDay = Math.max(
    localDayIndex((season.endDate ?? new Date()).getTime()),
    firstDay,
  );

  // Activity outside the declared window still has to appear, or the chart
  // totals would not match the season summary.
  if (observedDays.length > 0) {
    firstDay = Math.min(firstDay, ...observedDays);
    lastDay = Math.max(lastDay, ...observedDays);
  }

  const buckets = denseKeys(firstDay, lastDay, granularity).map(period => {
    const expense = quantizeMoney(expenseByBucket.get(period) ?? 0);
    const revenue = quantizeMoney(revenueByBucket.get(period) ?? 0);
    return {period, revenue, expense, profit: quantizeMoney(revenue - expense)};
  });

  const totalExpense = quantizeMoney(
    [...expenseByBucket.values()].reduce((s, v) => s + v, 0),
  );
  const totalRevenue = quantizeMoney(
    [...revenueByBucket.values()].reduce((s, v) => s + v, 0),
  );

  return {
    seasonId: season.id,
    seasonName: season.name,
    granularity,
    buckets,
    totals: {
      revenue: totalRevenue,
      expense: totalExpense,
      profit: quantizeMoney(totalRevenue - totalExpense),
    },
  };
}

// ═══════════════════════════════════════════════════════════════════════════
//  Biểu đồ 2 — Vật tư tiêu thụ
// ═══════════════════════════════════════════════════════════════════════════

export interface ConsumptionItem {
  key: string;
  label: string;
  quantity: number;
  /** null when the group mixes units — see unitMixed. */
  unit: string | null;
  unitMixed: boolean;
  totalCost: number;
  sharePct: number;
  transactionCount: number;
}

export interface SupplyConsumptionReport {
  seasonId: string | null;
  groupBy: GroupBy;
  items: ConsumptionItem[];
  totalCost: number;
}

export async function supplyConsumptionReport(
  database: Database,
  options: {seasonId?: string | null; groupBy?: GroupBy} = {},
): Promise<SupplyConsumptionReport> {
  const {seasonId = null, groupBy = 'category'} = options;

  // Only `out` movements. A stock-in is a purchase, not consumption;
  // including it would double the apparent usage of everything.
  const conditions = [Q.where('txn_type', TxnType.OUT)];
  if (seasonId) {
    conditions.push(Q.where('season_id', seasonId));
  }
  const movements = await database
    .get<StockTransaction>('stock_transactions')
    .query(...conditions)
    .fetch();

  const supplyIds = [...new Set(movements.map(m => m.supplyId))];
  const supplies = await database
    .get<Supply>('supplies')
    .query(Q.where('id', Q.oneOf(supplyIds)))
    .fetch();
  const supplyById = new Map(supplies.map(s => [s.id, s]));

  interface Bucket {
    quantity: number;
    totalCost: number;
    count: number;
    units: Set<string>;
    label: string;
  }
  const grouped = new Map<string, Bucket>();

  for (const movement of movements) {
    const supply = supplyById.get(movement.supplyId);
    if (!supply) {
      continue;
    }
    const key = groupBy === 'category' ? supply.category : supply.id;
    const label =
      groupBy === 'category'
        ? (SUPPLY_CATEGORY_LABELS[supply.category as SupplyCategory] ?? supply.category)
        : supply.name;

    const bucket = grouped.get(key) ?? {
      quantity: 0,
      totalCost: 0,
      count: 0,
      units: new Set<string>(),
      label,
    };
    bucket.quantity += movement.quantity;
    bucket.totalCost += movement.totalCost;
    bucket.count += 1;
    bucket.units.add(supply.unit);
    grouped.set(key, bucket);
  }

  const totalCost = quantizeMoney(
    [...grouped.values()].reduce((s, b) => s + b.totalCost, 0),
  );

  const items: ConsumptionItem[] = [...grouped.entries()]
    .map(([key, bucket]) => {
      const cost = quantizeMoney(bucket.totalCost);
      const mixed = bucket.units.size > 1;
      return {
        key,
        label: bucket.label,
        quantity: quantizeQuantity(bucket.quantity),
        // Suppressed when the group mixes units: reporting a single number
        // for a category holding both kg and litres is meaningless, and the
        // chart must fall back to cost.
        unit: mixed ? null : ([...bucket.units][0] ?? null),
        unitMixed: mixed,
        totalCost: cost,
        sharePct: totalCost > 0 ? Math.round((cost / totalCost) * 1000) / 10 : 0,
        transactionCount: bucket.count,
      };
    })
    .sort((a, b) => b.totalCost - a.totalCost);

  return {seasonId, groupBy, items, totalCost};
}

// ═══════════════════════════════════════════════════════════════════════════
//  Biểu đồ 3 — So sánh mùa vụ
// ═══════════════════════════════════════════════════════════════════════════

export interface SeasonComparisonItem {
  seasonId: string;
  name: string;
  cropType: string;
  status: SeasonStatus;
  startDate: number;
  revenue: number;
  expense: number;
  profit: number;
  marginPct: number | null;
}

export interface SeasonComparisonReport {
  seasons: SeasonComparisonItem[];
  bestSeasonId: string | null;
  worstSeasonId: string | null;
}

export async function seasonComparisonReport(
  database: Database,
  options: {limit?: number; status?: SeasonStatus} = {},
): Promise<SeasonComparisonReport> {
  const {limit = 10, status} = options;

  const conditions = status ? [Q.where('status', status)] : [];
  const allSeasons = await database
    .get<Season>('seasons')
    .query(...conditions, Q.sortBy('start_date', Q.desc))
    .fetch();
  const seasonsInScope = allSeasons.slice(0, limit);

  if (seasonsInScope.length === 0) {
    return {seasons: [], bestSeasonId: null, worstSeasonId: null};
  }

  const ids = seasonsInScope.map(s => s.id);
  const [expenses, revenues] = await Promise.all([
    database.get<Expense>('expenses').query(Q.where('season_id', Q.oneOf(ids))).fetch(),
    database.get<Revenue>('revenues').query(Q.where('season_id', Q.oneOf(ids))).fetch(),
  ]);

  const expenseBySeason = new Map<string, number>();
  const revenueBySeason = new Map<string, number>();
  for (const e of expenses) {
    expenseBySeason.set(e.seasonId, (expenseBySeason.get(e.seasonId) ?? 0) + e.amount);
  }
  for (const r of revenues) {
    revenueBySeason.set(r.seasonId, (revenueBySeason.get(r.seasonId) ?? 0) + r.amount);
  }

  // Seasons with no records still appear, at zero. A farmer comparing seasons
  // needs to see the one they just started, not have it silently missing.
  const seasons: SeasonComparisonItem[] = seasonsInScope.map(season => {
    const expense = quantizeMoney(expenseBySeason.get(season.id) ?? 0);
    const revenue = quantizeMoney(revenueBySeason.get(season.id) ?? 0);
    const profit = quantizeMoney(revenue - expense);
    return {
      seasonId: season.id,
      name: season.name,
      cropType: season.cropType,
      status: season.status,
      startDate: season.startDate.getTime(),
      revenue,
      expense,
      profit,
      marginPct: revenue > 0 ? Math.round((profit / revenue) * 1000) / 10 : null,
    };
  });

  const best = seasons.reduce((a, b) => (b.profit > a.profit ? b : a));
  const worst = seasons.reduce((a, b) => (b.profit < a.profit ? b : a));

  return {
    seasons,
    bestSeasonId: best.seasonId,
    worstSeasonId: worst.seasonId,
  };
}

export {EXPENSE_CATEGORY_LABELS};
