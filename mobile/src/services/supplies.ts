/**
 * Danh mục vật tư — local CRUD (Issue #24).
 *
 * Mirrors backend/app/services/supply_service.py, minus the parts that only
 * make sense server-side:
 *
 *   - `name_key` is not in the mobile schema. The server derives it and owns
 *     the unique index; the client does a best-effort duplicate check here to
 *     stop the same supply being typed twice on THIS device, and treats it as
 *     a hint rather than a rule.
 *   - Two devices creating the same supply while both offline is allowed to
 *     produce two rows (D5). Silently merging two entries a human may have
 *     meant as distinct is the worse failure.
 */

import {Database, Q} from '@nozbe/watermelondb';

import type {SupplyCategory} from '../db/enums';
import type {StockTransaction, Supply} from '../db/models';
import {quantizeMoney, quantizeQuantity} from '../utils/numeric';
import {ValidationError} from './seasons';

export interface SupplyInput {
  name: string;
  category: SupplyCategory;
  unit: string;
  unitCost?: number;
  lowStockThreshold?: number;
  note?: string | null;
}

/**
 * Case-insensitive fold for the local duplicate hint.
 *
 * Uses toLowerCase + NFC, the JavaScript counterpart of the server's
 * `normalise_key`. It does not have to match byte for byte — the server's
 * unique index is the authority — but it should agree in the ordinary case so
 * the farmer is not told "duplicate" here and then accepted there, or the
 * reverse.
 */
export function localNameKey(name: string): string {
  return name.normalize('NFC').trim().toLowerCase();
}

export function validateSupply(input: SupplyInput): void {
  if (!input.name.trim()) {
    throw new ValidationError('Tên vật tư không được để trống.');
  }
  if (input.name.trim().length > 120) {
    throw new ValidationError('Tên vật tư tối đa 120 ký tự.');
  }
  if (!input.unit.trim()) {
    throw new ValidationError('Đơn vị tính không được để trống.');
  }
  if (input.unitCost !== undefined && input.unitCost < 0) {
    throw new ValidationError('Đơn giá không được âm.');
  }
  if (input.lowStockThreshold !== undefined && input.lowStockThreshold < 0) {
    throw new ValidationError('Ngưỡng cảnh báo không được âm.');
  }
}

export function observeSupplies(database: Database, includeArchived = false) {
  const conditions = includeArchived ? [] : [Q.where('is_archived', false)];
  return database
    .get<Supply>('supplies')
    .query(...conditions, Q.sortBy('name', Q.asc))
    .observeWithColumns(['name', 'category', 'unit', 'unit_cost', 'is_archived']);
}

async function findDuplicate(
  database: Database,
  name: string,
  unit: string,
  excludeId?: string,
): Promise<Supply | null> {
  const key = localNameKey(name);
  const candidates = await database
    .get<Supply>('supplies')
    .query(Q.where('unit', unit.trim()))
    .fetch();

  return (
    candidates.find(s => s.id !== excludeId && localNameKey(s.name) === key) ?? null
  );
}

export async function createSupply(
  database: Database,
  input: SupplyInput,
): Promise<Supply> {
  validateSupply(input);

  const duplicate = await findDuplicate(database, input.name, input.unit);
  if (duplicate) {
    throw new ValidationError(
      `Vật tư "${duplicate.name}" (${duplicate.unit}) đã có trong danh mục.`,
    );
  }

  return database.write(() =>
    database.get<Supply>('supplies').create(s => {
      s.name = input.name.trim();
      s.category = input.category;
      s.unit = input.unit.trim();
      s.unitCost = quantizeMoney(input.unitCost ?? 0);
      s.lowStockThreshold = quantizeQuantity(input.lowStockThreshold ?? 0);
      s.isArchived = false;
      s.note = input.note ?? null;
    }),
  );
}

/**
 * Sửa vật tư.
 *
 * Changing `unitCost` affects FUTURE movements only. Every past transaction
 * keeps the price snapshotted when it happened, so updating today's price
 * cannot rewrite the cost history of a season that already closed.
 */
export async function updateSupply(
  database: Database,
  supplyId: string,
  patch: Partial<SupplyInput> & {isArchived?: boolean},
): Promise<Supply> {
  const supply = await database.get<Supply>('supplies').find(supplyId);

  validateSupply({
    name: patch.name ?? supply.name,
    category: patch.category ?? supply.category,
    unit: patch.unit ?? supply.unit,
    unitCost: patch.unitCost !== undefined ? patch.unitCost : supply.unitCost,
    lowStockThreshold:
      patch.lowStockThreshold !== undefined
        ? patch.lowStockThreshold
        : supply.lowStockThreshold,
  });

  const nextName = patch.name ?? supply.name;
  const nextUnit = patch.unit ?? supply.unit;
  if (localNameKey(nextName) !== localNameKey(supply.name) || nextUnit !== supply.unit) {
    const duplicate = await findDuplicate(database, nextName, nextUnit, supplyId);
    if (duplicate) {
      throw new ValidationError(
        `Vật tư "${duplicate.name}" (${duplicate.unit}) đã có trong danh mục.`,
      );
    }
  }

  return database.write(() =>
    supply.update(s => {
      if (patch.name !== undefined) {
        s.name = patch.name.trim();
      }
      if (patch.category !== undefined) {
        s.category = patch.category;
      }
      if (patch.unit !== undefined) {
        s.unit = patch.unit.trim();
      }
      if (patch.unitCost !== undefined) {
        s.unitCost = quantizeMoney(patch.unitCost);
      }
      if (patch.lowStockThreshold !== undefined) {
        s.lowStockThreshold = quantizeQuantity(patch.lowStockThreshold);
      }
      if (patch.isArchived !== undefined) {
        s.isArchived = patch.isArchived;
      }
      if (patch.note !== undefined) {
        s.note = patch.note;
      }
    }),
  );
}

export async function movementCount(
  database: Database,
  supplyId: string,
): Promise<number> {
  return database
    .get<StockTransaction>('stock_transactions')
    .query(Q.where('supply_id', supplyId))
    .fetchCount();
}

/**
 * Xoá vật tư — chỉ khi chưa từng có giao dịch kho.
 *
 * A supply with movement history must be archived instead. Two reasons, and
 * both are about OTHER devices rather than this one:
 *
 *   - a tombstone makes WatermelonDB drop the row everywhere, so last
 *     season's diary entries would render a blank supply name;
 *   - the ledger rows carry the prices past seasons were costed at, so
 *     removing the catalogue entry they point at rewrites that history.
 */
export async function deleteSupply(database: Database, supplyId: string): Promise<void> {
  const count = await movementCount(database, supplyId);
  if (count > 0) {
    throw new ValidationError(
      `Vật tư này đã có ${count} giao dịch kho nên không thể xoá. ` +
        'Hãy lưu trữ để ẩn khỏi danh sách mà vẫn giữ lịch sử.',
    );
  }
  const supply = await database.get<Supply>('supplies').find(supplyId);
  await database.write(() => supply.markAsDeleted());
}

export async function archiveSupply(
  database: Database,
  supplyId: string,
  archived = true,
): Promise<Supply> {
  return updateSupply(database, supplyId, {isArchived: archived});
}
