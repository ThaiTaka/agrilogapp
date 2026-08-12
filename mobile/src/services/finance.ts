/**
 * Thu chi — local CRUD (Issue #28).
 *
 * Mirrors backend/app/services/finance_service.py for the manual half. The
 * automatic half — expenses generated from supply consumption — belongs to
 * diary.ts and must not be reachable from here.
 *
 * That separation is the whole point of D7: a `diary_auto` expense is a
 * derived value. Letting it be edited here would make the generator and the
 * stored number diverge, and the next edit to the diary entry would either
 * overwrite the correction or not, depending on ordering. Refusing is the
 * only behaviour that stays predictable.
 */

import {Database, Q} from '@nozbe/watermelondb';

import {ExpenseCategory, ExpenseSource} from '../db/enums';
import type {Expense, Revenue} from '../db/models';
import {quantizeMoney, quantizeQuantity} from '../utils/numeric';
import {ValidationError} from './seasons';

// ─── Chi phí ────────────────────────────────────────────────────────────────

export interface ExpenseInput {
  seasonId: string;
  category: ExpenseCategory;
  amount: number;
  expenseDate?: Date;
  description?: string | null;
}

export function validateExpense(input: Pick<ExpenseInput, 'amount'>): void {
  if (!Number.isFinite(input.amount)) {
    throw new ValidationError('Số tiền không hợp lệ.');
  }
  if (input.amount < 0) {
    throw new ValidationError('Số tiền không được âm.');
  }
}

/**
 * Refuse to touch a generated expense.
 *
 * Called before every mutation rather than relying on the UI to hide the
 * button: the UI is a courtesy, this is the rule.
 */
function assertEditable(expense: Expense): void {
  if (expense.source === ExpenseSource.DIARY_AUTO) {
    throw new ValidationError(
      'Khoản chi này được tạo tự động từ nhật ký canh tác nên không sửa trực tiếp được. ' +
        'Hãy sửa lượng vật tư trong nhật ký tương ứng.',
    );
  }
}

export function observeExpenses(database: Database, seasonId: string) {
  return database
    .get<Expense>('expenses')
    .query(Q.where('season_id', seasonId), Q.sortBy('expense_date', Q.desc))
    .observeWithColumns(['amount', 'category', 'expense_date', 'description', 'source']);
}

export async function createExpense(
  database: Database,
  input: ExpenseInput,
): Promise<Expense> {
  validateExpense(input);

  return database.write(() =>
    database.get<Expense>('expenses').create(e => {
      e.seasonId = input.seasonId;
      // Never settable from a form. Only diary.ts may write diary_auto, and
      // a forged one would be a cost with no movement behind it — impossible
      // to reconcile when the entry it claims to belong to is edited.
      e.stockTransactionId = null;
      e.source = ExpenseSource.MANUAL;
      e.category = input.category;
      e.amount = quantizeMoney(input.amount);
      e.expenseDate = input.expenseDate ?? new Date();
      e.description = input.description ?? null;
    }),
  );
}

export async function updateExpense(
  database: Database,
  expenseId: string,
  patch: Partial<Omit<ExpenseInput, 'seasonId'>>,
): Promise<Expense> {
  const expense = await database.get<Expense>('expenses').find(expenseId);
  assertEditable(expense);

  if (patch.amount !== undefined) {
    validateExpense({amount: patch.amount});
  }

  return database.write(() =>
    expense.update(e => {
      if (patch.category !== undefined) {
        e.category = patch.category;
      }
      if (patch.amount !== undefined) {
        e.amount = quantizeMoney(patch.amount);
      }
      if (patch.expenseDate !== undefined) {
        e.expenseDate = patch.expenseDate;
      }
      if (patch.description !== undefined) {
        e.description = patch.description;
      }
    }),
  );
}

export async function deleteExpense(
  database: Database,
  expenseId: string,
): Promise<void> {
  const expense = await database.get<Expense>('expenses').find(expenseId);
  assertEditable(expense);
  await database.write(() => expense.markAsDeleted());
}

// ─── Doanh thu ──────────────────────────────────────────────────────────────

export interface RevenueInput {
  seasonId: string;
  quantity?: number | null;
  unit?: string | null;
  unitPrice?: number | null;
  /** Omit to derive from quantity × unitPrice. */
  amount?: number | null;
  revenueDate?: Date;
  buyer?: string | null;
  description?: string | null;
}

/**
 * Work out the authoritative total.
 *
 * An explicit `amount` always wins over the product. Real sales get rounded
 * down, discounted for moisture, or partly paid, and the number the farmer
 * was actually handed beats the number the arithmetic implies.
 */
export function resolveRevenueAmount(input: RevenueInput): number {
  if (input.amount !== null && input.amount !== undefined) {
    if (input.amount < 0) {
      throw new ValidationError('Số tiền không được âm.');
    }
    return quantizeMoney(input.amount);
  }
  if (
    input.quantity === null ||
    input.quantity === undefined ||
    input.unitPrice === null ||
    input.unitPrice === undefined
  ) {
    throw new ValidationError(
      'Cần nhập thành tiền, hoặc cả sản lượng và đơn giá để tính ra nó.',
    );
  }
  if (input.quantity < 0 || input.unitPrice < 0) {
    throw new ValidationError('Sản lượng và đơn giá không được âm.');
  }
  return quantizeMoney(input.quantity * input.unitPrice);
}

export function observeRevenues(database: Database, seasonId: string) {
  return database
    .get<Revenue>('revenues')
    .query(Q.where('season_id', seasonId), Q.sortBy('revenue_date', Q.desc))
    .observeWithColumns(['amount', 'quantity', 'unit_price', 'revenue_date', 'buyer']);
}

export async function createRevenue(
  database: Database,
  input: RevenueInput,
): Promise<Revenue> {
  const amount = resolveRevenueAmount(input);

  return database.write(() =>
    database.get<Revenue>('revenues').create(r => {
      r.seasonId = input.seasonId;
      r.quantity =
        input.quantity === null || input.quantity === undefined
          ? null
          : quantizeQuantity(input.quantity);
      r.unit = input.unit ?? null;
      r.unitPrice =
        input.unitPrice === null || input.unitPrice === undefined
          ? null
          : quantizeMoney(input.unitPrice);
      r.amount = amount;
      r.revenueDate = input.revenueDate ?? new Date();
      r.buyer = input.buyer ?? null;
      r.description = input.description ?? null;
    }),
  );
}

export async function updateRevenue(
  database: Database,
  revenueId: string,
  patch: Partial<Omit<RevenueInput, 'seasonId'>>,
): Promise<Revenue> {
  const revenue = await database.get<Revenue>('revenues').find(revenueId);

  return database.write(() =>
    revenue.update(r => {
      if (patch.quantity !== undefined) {
        r.quantity = patch.quantity === null ? null : quantizeQuantity(patch.quantity);
      }
      if (patch.unit !== undefined) {
        r.unit = patch.unit;
      }
      if (patch.unitPrice !== undefined) {
        r.unitPrice = patch.unitPrice === null ? null : quantizeMoney(patch.unitPrice);
      }
      if (patch.revenueDate !== undefined) {
        r.revenueDate = patch.revenueDate;
      }
      if (patch.buyer !== undefined) {
        r.buyer = patch.buyer;
      }
      if (patch.description !== undefined) {
        r.description = patch.description;
      }

      if (patch.amount !== undefined && patch.amount !== null) {
        r.amount = quantizeMoney(patch.amount);
      } else if (
        (patch.quantity !== undefined || patch.unitPrice !== undefined) &&
        r.quantity !== null &&
        r.unitPrice !== null
      ) {
        // Quantity or price moved and the farmer did not restate the total,
        // so recompute. An explicit amount above always takes precedence.
        r.amount = quantizeMoney(r.quantity * r.unitPrice);
      }
    }),
  );
}

export async function deleteRevenue(
  database: Database,
  revenueId: string,
): Promise<void> {
  const revenue = await database.get<Revenue>('revenues').find(revenueId);
  await database.write(() => revenue.markAsDeleted());
}

// ─── Tổng kết ───────────────────────────────────────────────────────────────

export interface CostBreakdown {
  category: ExpenseCategory;
  amount: number;
  sharePct: number;
}

export interface FinanceSummary {
  totalCost: number;
  totalRevenue: number;
  profit: number;
  marginPct: number | null;
  autoGeneratedCost: number;
  manualCost: number;
  expenseCount: number;
  revenueCount: number;
  costByCategory: CostBreakdown[];
}

/**
 * Profit is computed, never stored (I10).
 *
 * The auto/manual split is surfaced because the two mean different things to
 * a farmer: manual costs are things they chose to record, auto costs appeared
 * by themselves out of the diary. Seeing the split is how they come to trust
 * the automatic half.
 */
export async function financeSummary(
  database: Database,
  seasonId: string,
): Promise<FinanceSummary> {
  const [expenses, revenues] = await Promise.all([
    database.get<Expense>('expenses').query(Q.where('season_id', seasonId)).fetch(),
    database.get<Revenue>('revenues').query(Q.where('season_id', seasonId)).fetch(),
  ]);

  const totalCost = quantizeMoney(expenses.reduce((s, e) => s + e.amount, 0));
  const totalRevenue = quantizeMoney(revenues.reduce((s, r) => s + r.amount, 0));
  const profit = quantizeMoney(totalRevenue - totalCost);

  const autoGeneratedCost = quantizeMoney(
    expenses
      .filter(e => e.source === ExpenseSource.DIARY_AUTO)
      .reduce((s, e) => s + e.amount, 0),
  );

  const byCategory = new Map<ExpenseCategory, number>();
  for (const expense of expenses) {
    byCategory.set(expense.category, (byCategory.get(expense.category) ?? 0) + expense.amount);
  }

  const costByCategory: CostBreakdown[] = [...byCategory.entries()]
    .map(([category, amount]) => ({
      category,
      amount: quantizeMoney(amount),
      sharePct: totalCost > 0 ? Math.round((amount / totalCost) * 1000) / 10 : 0,
    }))
    .sort((a, b) => b.amount - a.amount);

  return {
    totalCost,
    totalRevenue,
    profit,
    // null rather than 0: "no margin computed" and "zero margin" are
    // different facts, and a farmer reading "0%" would conclude they broke
    // even rather than that they have not sold anything yet.
    marginPct: totalRevenue > 0 ? Math.round((profit / totalRevenue) * 1000) / 10 : null,
    autoGeneratedCost,
    manualCost: quantizeMoney(totalCost - autoGeneratedCost),
    expenseCount: expenses.length,
    revenueCount: revenues.length,
    costByCategory,
  };
}
