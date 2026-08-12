/**
 * Offline stock restore and auto expense (Issues #26, #29).
 *
 * These run against a real WatermelonDB and assert the same invariants the
 * backend suite does, with the same numbers. The point is symmetry: a farmer
 * who edits an entry in airplane mode and a farmer who edits it online must
 * end up with identical inventory and identical costs, or the two diverge
 * silently at the next sync.
 *
 *   I3  create → edit → delete returns on-hand to EXACTLY its prior value
 *   I4  the restore is idempotent
 *   I6  exactly one expense per supply-consuming movement
 *   I7  a bare stock-out generates no expense
 */

import {Database, Q} from '@nozbe/watermelondb';

import {ExpenseSource, SeasonStatus, SupplyCategory, WorkType} from '../../db/enums';
import type {Expense, Season, StockTransaction, Supply} from '../../db/models';
import {
  createDiaryEntry,
  deleteDiaryEntry,
  entrySupplyCost,
  updateDiaryEntry,
} from '../diary';
import {recordStockIn, recordStockOut, recordStockTake, stockLevel} from '../stock';
import {createTestDatabase} from './testDatabase';

let db: Database;
let season: Season;
let urea: Supply;
let regent: Supply;

async function seed() {
  db = createTestDatabase();

  await db.write(async () => {
    season = await db.get<Season>('seasons').create(s => {
      s.name = 'Vụ Đông Xuân 2026';
      s.cropType = 'Lúa';
      s.areaSize = 5;
      s.areaUnit = 'sao';
      s.startDate = new Date('2026-12-01T03:00:00Z');
      s.endDate = null;
      s.status = SeasonStatus.ACTIVE;
      s.note = null;
    });

    urea = await db.get<Supply>('supplies').create(s => {
      s.name = 'Đạm Urê';
      s.category = SupplyCategory.FERTILIZER;
      s.unit = 'kg';
      s.unitCost = 12_000;
      s.lowStockThreshold = 20;
      s.isArchived = false;
      s.note = null;
    });

    regent = await db.get<Supply>('supplies').create(s => {
      s.name = 'Thuốc Regent';
      s.category = SupplyCategory.PESTICIDE;
      s.unit = 'chai';
      s.unitCost = 45_000;
      s.lowStockThreshold = 0;
      s.isArchived = false;
      s.note = null;
    });
  });

  await recordStockIn(db, {supplyId: urea.id, quantity: 100});
  await recordStockIn(db, {supplyId: regent.id, quantity: 10});
}

async function autoExpenses(entryId: string): Promise<Expense[]> {
  const txns = await db
    .get<StockTransaction>('stock_transactions')
    .query(Q.where('diary_entry_id', entryId))
    .fetch();

  const out: Expense[] = [];
  for (const txn of txns) {
    const rows = await db
      .get<Expense>('expenses')
      .query(Q.where('stock_transaction_id', txn.id))
      .fetch();
    out.push(...rows);
  }
  return out;
}

async function allExpenses(): Promise<Expense[]> {
  return db.get<Expense>('expenses').query().fetch();
}

beforeEach(seed);

// ═══════════════════════════════════════════════════════════════════════════
//  Mức tồn kho
// ═══════════════════════════════════════════════════════════════════════════

describe('Tồn kho tính từ sổ cái', () => {
  it('nhập kho cộng vào', async () => {
    expect(await stockLevel(db, urea.id)).toBe(100);
  });

  it('xuất kho trừ đi', async () => {
    await recordStockOut(db, {supplyId: urea.id, quantity: 12.5});
    expect(await stockLevel(db, urea.id)).toBe(87.5);
  });

  it('cộng đúng qua nhiều giao dịch lẻ', async () => {
    for (const q of [10.5, 20.25, 0.125]) {
      await recordStockIn(db, {supplyId: urea.id, quantity: q});
    }
    for (const q of [5.375, 1.5]) {
      await recordStockOut(db, {supplyId: urea.id, quantity: q});
    }
    expect(await stockLevel(db, urea.id)).toBe(124);
  });

  it('cho phép tồn âm và không chặn (I2)', async () => {
    await recordStockOut(db, {supplyId: regent.id, quantity: 15});
    expect(await stockLevel(db, regent.id)).toBe(-5);
  });

  it('không lưu bộ đếm nào trên vật tư (D1)', async () => {
    const supply = await db.get<Supply>('supplies').find(urea.id);
    expect(Object.keys(supply._raw)).not.toContain('current_stock');
  });
});

describe('Kiểm kê', () => {
  it('đếm nhiều hơn sổ sách sinh delta dương', async () => {
    const {delta} = await recordStockTake(db, urea.id, 105);
    expect(delta).toBe(5);
    expect(await stockLevel(db, urea.id)).toBe(105);
  });

  it('đếm ít hơn sinh delta âm', async () => {
    const {delta} = await recordStockTake(db, urea.id, 92.5);
    expect(delta).toBe(-7.5);
    expect(await stockLevel(db, urea.id)).toBe(92.5);
  });

  it('đếm khớp thì không ghi gì', async () => {
    // A no-op row would bump updated_at and manufacture a phantom conflict
    // for another device editing the same supply.
    const before = (
      await db.get<StockTransaction>('stock_transactions').query().fetch()
    ).length;

    const {transaction, delta} = await recordStockTake(db, urea.id, 100);

    expect(transaction).toBeNull();
    expect(delta).toBe(0);
    const after = (
      await db.get<StockTransaction>('stock_transactions').query().fetch()
    ).length;
    expect(after).toBe(before);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
//  Nhật ký và tiêu thụ vật tư
// ═══════════════════════════════════════════════════════════════════════════

describe('Ghi nhật ký kèm vật tư', () => {
  it('trừ kho ngay', async () => {
    await createDiaryEntry(db, {
      seasonId: season.id,
      workType: WorkType.FERTILIZING,
      supplyUsages: [{supplyId: urea.id, quantity: 25.5}],
    });
    expect(await stockLevel(db, urea.id)).toBe(74.5);
  });

  it('chụp ảnh giá tại thời điểm dùng', async () => {
    const entry = await createDiaryEntry(db, {
      seasonId: season.id,
      workType: WorkType.FERTILIZING,
      supplyUsages: [{supplyId: urea.id, quantity: 10}],
    });
    expect(await entrySupplyCost(db, entry.id)).toBe(120_000);

    // Đổi giá catalogue — lịch sử không được thay đổi.
    await db.write(() => urea.update(s => (s.unitCost = 99_000)));
    expect(await entrySupplyCost(db, entry.id)).toBe(120_000);
  });

  it('nhiều vật tư trong một nhật ký', async () => {
    await createDiaryEntry(db, {
      seasonId: season.id,
      workType: WorkType.SPRAYING,
      supplyUsages: [
        {supplyId: urea.id, quantity: 10},
        {supplyId: regent.id, quantity: 2},
      ],
    });
    expect(await stockLevel(db, urea.id)).toBe(90);
    expect(await stockLevel(db, regent.id)).toBe(8);
  });

  it('từ chối hai dòng cùng một vật tư', async () => {
    await expect(
      createDiaryEntry(db, {
        seasonId: season.id,
        workType: WorkType.FERTILIZING,
        supplyUsages: [
          {supplyId: urea.id, quantity: 10},
          {supplyId: urea.id, quantity: 5},
        ],
      }),
    ).rejects.toThrow('một dòng');
  });
});

// ═══════════════════════════════════════════════════════════════════════════
//  Hoàn kho (#26)
// ═══════════════════════════════════════════════════════════════════════════

describe('Hoàn kho khi sửa nhật ký', () => {
  it('tăng số lượng thì trừ thêm', async () => {
    const entry = await createDiaryEntry(db, {
      seasonId: season.id,
      workType: WorkType.FERTILIZING,
      supplyUsages: [{supplyId: urea.id, quantity: 10}],
    });
    await updateDiaryEntry(db, entry.id, {
      supplyUsages: [{supplyId: urea.id, quantity: 30}],
    });
    expect(await stockLevel(db, urea.id)).toBe(70);
  });

  it('giảm số lượng thì trả lại kho', async () => {
    const entry = await createDiaryEntry(db, {
      seasonId: season.id,
      workType: WorkType.FERTILIZING,
      supplyUsages: [{supplyId: urea.id, quantity: 30}],
    });
    await updateDiaryEntry(db, entry.id, {
      supplyUsages: [{supplyId: urea.id, quantity: 10}],
    });
    expect(await stockLevel(db, urea.id)).toBe(90);
  });

  it('bỏ một vật tư thì hoàn toàn bộ lượng đó', async () => {
    const entry = await createDiaryEntry(db, {
      seasonId: season.id,
      workType: WorkType.SPRAYING,
      supplyUsages: [
        {supplyId: urea.id, quantity: 10},
        {supplyId: regent.id, quantity: 3},
      ],
    });
    await updateDiaryEntry(db, entry.id, {
      supplyUsages: [{supplyId: urea.id, quantity: 10}],
    });
    expect(await stockLevel(db, regent.id)).toBe(10);
    expect(await stockLevel(db, urea.id)).toBe(90);
  });

  it('danh sách rỗng thì hoàn tất cả', async () => {
    const entry = await createDiaryEntry(db, {
      seasonId: season.id,
      workType: WorkType.FERTILIZING,
      supplyUsages: [{supplyId: urea.id, quantity: 40}],
    });
    await updateDiaryEntry(db, entry.id, {supplyUsages: []});
    expect(await stockLevel(db, urea.id)).toBe(100);
  });

  it('không truyền supplyUsages thì giữ nguyên', async () => {
    // Collapsing "omitted" and "[]" would make fixing a typo in the note
    // silently wipe the fertiliser record.
    const entry = await createDiaryEntry(db, {
      seasonId: season.id,
      workType: WorkType.FERTILIZING,
      supplyUsages: [{supplyId: urea.id, quantity: 40}],
    });
    await updateDiaryEntry(db, entry.id, {note: 'sửa ghi chú'});
    expect(await stockLevel(db, urea.id)).toBe(60);
  });

  it('sửa mà không đổi gì thì không ghi lại dòng cũ', async () => {
    // A no-op write bumps updated_at, which drives last-write-wins — it would
    // manufacture a conflict against another device that legitimately edited
    // the same row, and that device's edit would lose.
    const entry = await createDiaryEntry(db, {
      seasonId: season.id,
      workType: WorkType.FERTILIZING,
      supplyUsages: [{supplyId: urea.id, quantity: 10}],
    });
    const txn = (
      await db
        .get<StockTransaction>('stock_transactions')
        .query(Q.where('diary_entry_id', entry.id))
        .fetch()
    )[0]!;
    const before = txn.updatedAt.getTime();

    await new Promise<void>(resolve => {
      setTimeout(() => resolve(), 5);
    });
    await updateDiaryEntry(db, entry.id, {
      supplyUsages: [{supplyId: urea.id, quantity: 10}],
    });

    const after = await db.get<StockTransaction>('stock_transactions').find(txn.id);
    expect(after.updatedAt.getTime()).toBe(before);
  });

  it('đổi ngày thì kéo giao dịch theo', async () => {
    const entry = await createDiaryEntry(db, {
      seasonId: season.id,
      workType: WorkType.FERTILIZING,
      entryDate: new Date('2026-12-05T03:00:00Z'),
      supplyUsages: [{supplyId: urea.id, quantity: 10}],
    });
    const newDate = new Date('2026-12-20T03:00:00Z');
    await updateDiaryEntry(db, entry.id, {entryDate: newDate});

    const txn = (
      await db
        .get<StockTransaction>('stock_transactions')
        .query(Q.where('diary_entry_id', entry.id))
        .fetch()
    )[0]!;
    expect(txn.txnDate.getTime()).toBe(newDate.getTime());
  });
});

describe('Hoàn kho khi xoá nhật ký', () => {
  it('trả lại toàn bộ vật tư', async () => {
    const entry = await createDiaryEntry(db, {
      seasonId: season.id,
      workType: WorkType.SPRAYING,
      supplyUsages: [
        {supplyId: urea.id, quantity: 25},
        {supplyId: regent.id, quantity: 3},
      ],
    });

    const result = await deleteDiaryEntry(db, entry.id);

    expect(result.transactionsReversed).toBe(2);
    expect(result.quantityRestored.get(urea.id)).toBe(25);
    expect(await stockLevel(db, urea.id)).toBe(100);
    expect(await stockLevel(db, regent.id)).toBe(10);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
//  Bất biến I3 / I4
// ═══════════════════════════════════════════════════════════════════════════

describe('Bất biến I3 — vòng đời trả tồn kho về đúng giá trị cũ', () => {
  it('tạo → sửa hai lần → xoá là trung tính tuyệt đối', async () => {
    const beforeUrea = await stockLevel(db, urea.id);
    const beforeRegent = await stockLevel(db, regent.id);

    const entry = await createDiaryEntry(db, {
      seasonId: season.id,
      workType: WorkType.FERTILIZING,
      supplyUsages: [
        {supplyId: urea.id, quantity: 33.333},
        {supplyId: regent.id, quantity: 1.5},
      ],
    });
    await updateDiaryEntry(db, entry.id, {
      supplyUsages: [{supplyId: urea.id, quantity: 12.125}],
    });
    await updateDiaryEntry(db, entry.id, {
      supplyUsages: [
        {supplyId: urea.id, quantity: 0.001},
        {supplyId: regent.id, quantity: 9.999},
      ],
    });
    await deleteDiaryEntry(db, entry.id);

    expect(await stockLevel(db, urea.id)).toBe(beforeUrea);
    expect(await stockLevel(db, regent.id)).toBe(beforeRegent);
  });

  it('số lẻ ba chữ số không tích luỹ sai số', async () => {
    const before = await stockLevel(db, urea.id);
    for (const q of [0.001, 33.333, 0.007, 66.659]) {
      const entry = await createDiaryEntry(db, {
        seasonId: season.id,
        workType: WorkType.FERTILIZING,
        supplyUsages: [{supplyId: urea.id, quantity: q}],
      });
      await deleteDiaryEntry(db, entry.id);
    }
    expect(await stockLevel(db, urea.id)).toBe(before);
  });

  it('I4 — sửa lặp lại cùng giá trị là idempotent', async () => {
    const entry = await createDiaryEntry(db, {
      seasonId: season.id,
      workType: WorkType.FERTILIZING,
      supplyUsages: [{supplyId: urea.id, quantity: 10}],
    });
    for (let i = 0; i < 5; i++) {
      await updateDiaryEntry(db, entry.id, {
        supplyUsages: [{supplyId: urea.id, quantity: 17.5}],
      });
    }
    expect(await stockLevel(db, urea.id)).toBe(82.5);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
//  Chi phí tự sinh (#29)
// ═══════════════════════════════════════════════════════════════════════════

describe('Chi phí tự sinh từ nhật ký', () => {
  it('mỗi lần tiêu thụ sinh đúng một chi phí', async () => {
    const entry = await createDiaryEntry(db, {
      seasonId: season.id,
      workType: WorkType.FERTILIZING,
      supplyUsages: [{supplyId: urea.id, quantity: 25}],
    });

    const rows = await autoExpenses(entry.id);
    expect(rows).toHaveLength(1);
    expect(rows[0]!.amount).toBe(300_000);
    expect(rows[0]!.source).toBe(ExpenseSource.DIARY_AUTO);
    expect(rows[0]!.seasonId).toBe(season.id);
    expect(rows[0]!.isEditable).toBe(false);
  });

  it('sửa số lượng thì cập nhật chi phí', async () => {
    const entry = await createDiaryEntry(db, {
      seasonId: season.id,
      workType: WorkType.FERTILIZING,
      supplyUsages: [{supplyId: urea.id, quantity: 10}],
    });
    await updateDiaryEntry(db, entry.id, {
      supplyUsages: [{supplyId: urea.id, quantity: 20}],
    });

    const rows = await autoExpenses(entry.id);
    expect(rows).toHaveLength(1);
    expect(rows[0]!.amount).toBe(240_000);
  });

  it('I6 — sửa năm lần vẫn đúng một chi phí', async () => {
    const entry = await createDiaryEntry(db, {
      seasonId: season.id,
      workType: WorkType.FERTILIZING,
      supplyUsages: [{supplyId: urea.id, quantity: 10}],
    });
    for (const q of [11, 12, 12, 13, 13]) {
      await updateDiaryEntry(db, entry.id, {
        supplyUsages: [{supplyId: urea.id, quantity: q}],
      });
    }
    const rows = await autoExpenses(entry.id);
    expect(rows).toHaveLength(1);
    expect(rows[0]!.amount).toBe(156_000);
  });

  it('bỏ vật tư thì xoá chi phí', async () => {
    const entry = await createDiaryEntry(db, {
      seasonId: season.id,
      workType: WorkType.FERTILIZING,
      supplyUsages: [{supplyId: urea.id, quantity: 10}],
    });
    await updateDiaryEntry(db, entry.id, {supplyUsages: []});
    expect(await autoExpenses(entry.id)).toHaveLength(0);
  });

  it('xoá nhật ký thì xoá chi phí', async () => {
    const entry = await createDiaryEntry(db, {
      seasonId: season.id,
      workType: WorkType.FERTILIZING,
      supplyUsages: [{supplyId: urea.id, quantity: 10}],
    });
    const result = await deleteDiaryEntry(db, entry.id);
    expect(result.expensesRemoved).toBe(1);
    expect(await autoExpenses(entry.id)).toHaveLength(0);
  });

  it('I7 — xuất kho trực tiếp không sinh chi phí', async () => {
    // Tiền đã ra khỏi nhà khi mua vật tư; ghi lại lần nữa là tính hai lần.
    await recordStockOut(db, {supplyId: urea.id, quantity: 5});
    expect(await allExpenses()).toHaveLength(0);
  });

  it('nhập kho không sinh chi phí', async () => {
    await recordStockIn(db, {supplyId: urea.id, quantity: 50});
    expect(await allExpenses()).toHaveLength(0);
  });

  it('tổng chi phí tự sinh khớp tổng tiêu thụ', async () => {
    const entry = await createDiaryEntry(db, {
      seasonId: season.id,
      workType: WorkType.SPRAYING,
      supplyUsages: [
        {supplyId: urea.id, quantity: 3.333},
        {supplyId: regent.id, quantity: 2},
      ],
    });

    const rows = await autoExpenses(entry.id);
    const total = rows.reduce((sum, e) => sum + e.amount, 0);
    expect(total).toBe(await entrySupplyCost(db, entry.id));
  });
});
