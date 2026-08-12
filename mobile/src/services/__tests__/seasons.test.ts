/**
 * Season CRUD and the deletion cascade (Issue #20).
 *
 * The cascade is the interesting part: it is deliberately asymmetric, and
 * getting it wrong destroys a purchase the farmer actually made.
 */

import {Database, Q} from '@nozbe/watermelondb';

import {SeasonStatus, SupplyCategory, WorkType} from '../../db/enums';
import type {DiaryEntry, Expense, Season, StockTransaction, Supply} from '../../db/models';
import {createDiaryEntry} from '../diary';
import {
  createSeason,
  deleteSeason,
  seasonTotals,
  updateSeason,
  validateSeason,
  ValidationError,
} from '../seasons';
import {recordStockIn, stockLevel} from '../stock';
import {createTestDatabase} from './testDatabase';

let db: Database;

const START = new Date('2026-12-01T03:00:00Z');

beforeEach(() => {
  db = createTestDatabase();
});

function baseInput() {
  return {name: 'Vụ Đông Xuân 2026', cropType: 'Lúa', startDate: START};
}

// ═══════════════════════════════════════════════════════════════════════════
//  Kiểm tra hợp lệ
// ═══════════════════════════════════════════════════════════════════════════

describe('validateSeason', () => {
  it('từ chối tên rỗng', () => {
    expect(() => validateSeason({...baseInput(), name: '   '})).toThrow(ValidationError);
  });

  it('từ chối thiếu loại cây trồng', () => {
    expect(() => validateSeason({...baseInput(), cropType: ''})).toThrow(ValidationError);
  });

  it('từ chối diện tích âm', () => {
    expect(() => validateSeason({...baseInput(), areaSize: -1})).toThrow(ValidationError);
  });

  it('từ chối ngày kết thúc trước ngày bắt đầu', () => {
    expect(() =>
      validateSeason({...baseInput(), endDate: new Date(START.getTime() - 1)}),
    ).toThrow('Ngày kết thúc');
  });

  it('cho phép mùa vụ chưa kết thúc', () => {
    expect(() => validateSeason({...baseInput(), endDate: null})).not.toThrow();
  });
});

describe('Tạo và sửa', () => {
  it('tạo với giá trị mặc định', async () => {
    const season = await createSeason(db, baseInput());
    expect(season.name).toBe('Vụ Đông Xuân 2026');
    expect(season.areaUnit).toBe('sao');
    expect(season.status).toBe(SeasonStatus.ACTIVE);
    expect(season.endDate).toBeNull();
  });

  it('cắt khoảng trắng thừa', async () => {
    const season = await createSeason(db, {...baseInput(), name: '  Vụ Mùa  '});
    expect(season.name).toBe('Vụ Mùa');
  });

  it('làm tròn diện tích về 3 chữ số', async () => {
    const season = await createSeason(db, {...baseInput(), areaSize: 5.00049});
    expect(season.areaSize).toBe(5);
  });

  it('sửa từng phần, không đụng phần còn lại', async () => {
    const season = await createSeason(db, {...baseInput(), note: 'ghi chú gốc'});
    await updateSeason(db, season.id, {status: SeasonStatus.HARVESTED});

    const fresh = await db.get<Season>('seasons').find(season.id);
    expect(fresh.status).toBe(SeasonStatus.HARVESTED);
    expect(fresh.note).toBe('ghi chú gốc');
    expect(fresh.cropType).toBe('Lúa');
  });

  it('kiểm tra khoảng ngày dựa trên bản ghi đã hợp nhất', async () => {
    // Sending only endDate must still be checked against the STORED
    // startDate, not against nothing.
    const season = await createSeason(db, baseInput());
    await expect(
      updateSeason(db, season.id, {endDate: new Date(START.getTime() - 1)}),
    ).rejects.toThrow('Ngày kết thúc');
  });
});

// ═══════════════════════════════════════════════════════════════════════════
//  Cascade khi xoá
// ═══════════════════════════════════════════════════════════════════════════

describe('Xoá mùa vụ', () => {
  async function seedSeasonWithData() {
    const season = await createSeason(db, baseInput());

    const urea = await db.write(() =>
      db.get<Supply>('supplies').create(s => {
        s.name = 'Đạm Urê';
        s.category = SupplyCategory.FERTILIZER;
        s.unit = 'kg';
        s.unitCost = 12_000;
        s.lowStockThreshold = 0;
        s.isArchived = false;
        s.note = null;
      }),
    );
    await recordStockIn(db, {supplyId: urea.id, quantity: 100});

    // Một lần mua ghi vào mùa vụ — KHÔNG gắn nhật ký.
    await recordStockIn(db, {
      supplyId: urea.id,
      quantity: 40,
      seasonId: season.id,
    });

    // Một nhật ký có dùng vật tư.
    await createDiaryEntry(db, {
      seasonId: season.id,
      workType: WorkType.FERTILIZING,
      supplyUsages: [{supplyId: urea.id, quantity: 30}],
    });

    return {season, urea};
  }

  it('hoàn kho phần vật tư đã dùng trong nhật ký', async () => {
    const {season, urea} = await seedSeasonWithData();
    expect(await stockLevel(db, urea.id)).toBe(110); // 100 + 40 − 30

    const result = await deleteSeason(db, season.id);

    expect(result.diaryEntries).toBe(1);
    expect(result.transactionsReversed).toBe(1);
    expect(await stockLevel(db, urea.id)).toBe(140); // 30 quay lại kho
  });

  it('giữ lại lần mua độc lập, chỉ gỡ liên kết mùa vụ', async () => {
    // The fertiliser is still physically in the shed. Deleting the purchase
    // would erase a transaction that really happened and silently change the
    // on-hand quantity.
    const {season, urea} = await seedSeasonWithData();

    const result = await deleteSeason(db, season.id);
    expect(result.transactionsUnlinked).toBe(1);

    const remaining = await db
      .get<StockTransaction>('stock_transactions')
      .query(Q.where('supply_id', urea.id))
      .fetch();

    const purchase = remaining.find(t => t.quantity === 40);
    expect(purchase).toBeDefined();
    expect(purchase!.seasonId).toBeNull();
  });

  it('xoá nhật ký và chi phí tự sinh theo', async () => {
    const {season} = await seedSeasonWithData();
    await deleteSeason(db, season.id);

    const entries = await db.get<DiaryEntry>('diary_entries').query().fetch();
    const expenses = await db.get<Expense>('expenses').query().fetch();
    expect(entries).toHaveLength(0);
    expect(expenses).toHaveLength(0);
  });

  it('mùa vụ biến mất khỏi danh sách', async () => {
    const {season} = await seedSeasonWithData();
    await deleteSeason(db, season.id);
    expect(await db.get<Season>('seasons').query().fetchCount()).toBe(0);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
//  Tổng kết tài chính
// ═══════════════════════════════════════════════════════════════════════════

describe('seasonTotals', () => {
  it('mùa vụ rỗng cho 0 và không có biên lợi nhuận', async () => {
    const season = await createSeason(db, baseInput());
    const totals = await seasonTotals(db, season.id);

    expect(totals.totalCost).toBe(0);
    expect(totals.profit).toBe(0);
    // null chứ không phải 0: "chưa tính được" khác "bằng không".
    expect(totals.marginPct).toBeNull();
  });

  it('I9 — chi phí vật tư vào tổng đúng một lần', async () => {
    const season = await createSeason(db, baseInput());
    const urea = await db.write(() =>
      db.get<Supply>('supplies').create(s => {
        s.name = 'Đạm Urê';
        s.category = SupplyCategory.FERTILIZER;
        s.unit = 'kg';
        s.unitCost = 12_000;
        s.lowStockThreshold = 0;
        s.isArchived = false;
        s.note = null;
      }),
    );
    await recordStockIn(db, {supplyId: urea.id, quantity: 100});

    await createDiaryEntry(db, {
      seasonId: season.id,
      workType: WorkType.FERTILIZING,
      supplyUsages: [{supplyId: urea.id, quantity: 25}],
    });

    const totals = await seasonTotals(db, season.id);
    expect(totals.totalCost).toBe(300_000);
    expect(totals.profit).toBe(-300_000);
  });
});
