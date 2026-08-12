/**
 * Ba biểu đồ báo cáo (Issues #43–#47).
 *
 * The centrepiece is TestGoldenParity: it rebuilds the backend's fixture
 * scenario in local WatermelonDB, runs the local reducers, and asserts the
 * result matches docs/reports_golden.json — the SAME file
 * backend/tests/test_reports.py generates and asserts.
 *
 * That is what turns "the chart shows the same number offline and online"
 * from an aspiration into a tested property (§11.4). Neither suite can catch
 * a divergence alone: each one is internally consistent while the two sides
 * quietly drift apart, and the farmer sees one number in the field and a
 * different one after syncing.
 */

import {Database} from '@nozbe/watermelondb';

import {
  ExpenseCategory,
  SeasonStatus,
  SupplyCategory,
  WorkType,
} from '../../db/enums';
import type {Season} from '../../db/models';
import {createDiaryEntry} from '../diary';
import {createExpense, createRevenue} from '../finance';
import {
  incomeExpenseReport,
  seasonComparisonReport,
  supplyConsumptionReport,
} from '../reports';
import {createSeason, updateSeason} from '../seasons';
import {recordStockIn, recordStockOut} from '../stock';
import {createSupply} from '../supplies';
import {createTestDatabase} from './testDatabase';

const golden = require('../../../../docs/reports_golden.json') as {
  season_name: string;
  granularity: string;
  buckets: {period: string; revenue: string; expense: string; profit: string}[];
  totals: {revenue: string; expense: string; profit: string};
};

let db: Database;

/** Epoch ms for a Vietnam-local date; mirrors the backend fixture's `ms()`. */
function ms(y: number, m: number, d: number, hour = 3): number {
  return Date.UTC(y, m - 1, d, hour);
}

beforeEach(() => {
  db = createTestDatabase();
});

// ═══════════════════════════════════════════════════════════════════════════
//  Song song với backend qua golden fixture (§11.4)
// ═══════════════════════════════════════════════════════════════════════════

describe('Golden fixture — cùng số liệu với backend', () => {
  /** Exactly the scenario in backend/tests/test_reports.py::scenario. */
  async function buildScenario(): Promise<Season> {
    const season = await createSeason(db, {
      name: 'Vụ Đông Xuân 2026-2027',
      cropType: 'Lúa',
      startDate: new Date(ms(2026, 12, 1)),
      endDate: new Date(ms(2027, 2, 28)),
    });

    await createExpense(db, {
      seasonId: season.id,
      category: ExpenseCategory.LABOR,
      amount: 2_000_000,
      expenseDate: new Date(ms(2026, 12, 5)),
    });
    await createExpense(db, {
      seasonId: season.id,
      category: ExpenseCategory.TRANSPORT,
      amount: 1_000_000,
      expenseDate: new Date(ms(2027, 2, 10)),
    });
    await createRevenue(db, {
      seasonId: season.id,
      amount: 12_000_000,
      revenueDate: new Date(ms(2027, 2, 20)),
    });

    return season;
  }

  it('tổng khớp từng đồng với fixture', async () => {
    const season = await buildScenario();
    const report = await incomeExpenseReport(db, season.id, 'month');

    expect(report.totals.revenue).toBe(Number(golden.totals.revenue));
    expect(report.totals.expense).toBe(Number(golden.totals.expense));
    expect(report.totals.profit).toBe(Number(golden.totals.profit));
  });

  it('các mốc thời gian khớp fixture, kể cả tháng rỗng', async () => {
    const season = await buildScenario();
    const report = await incomeExpenseReport(db, season.id, 'month');

    expect(report.buckets.map(b => b.period)).toEqual(
      golden.buckets.map(b => b.period),
    );
  });

  it('từng giá trị trong mỗi mốc khớp fixture', async () => {
    const season = await buildScenario();
    const report = await incomeExpenseReport(db, season.id, 'month');

    for (const expected of golden.buckets) {
      const actual = report.buckets.find(b => b.period === expected.period)!;
      expect(actual).toBeDefined();
      expect(actual.revenue).toBe(Number(expected.revenue));
      expect(actual.expense).toBe(Number(expected.expense));
      expect(actual.profit).toBe(Number(expected.profit));
    }
  });

  it('tên mùa vụ khớp fixture', async () => {
    const season = await buildScenario();
    const report = await incomeExpenseReport(db, season.id, 'month');
    expect(report.seasonName).toBe(golden.season_name);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
//  Biểu đồ 1
// ═══════════════════════════════════════════════════════════════════════════

describe('Biểu đồ 1 — Thu chi theo thời gian', () => {
  async function seasonWithGap(): Promise<Season> {
    const season = await createSeason(db, {
      name: 'Vụ có tháng trống',
      cropType: 'Lúa',
      startDate: new Date(ms(2026, 12, 1)),
      endDate: new Date(ms(2027, 2, 28)),
    });
    await createExpense(db, {
      seasonId: season.id,
      category: ExpenseCategory.LABOR,
      amount: 1_000_000,
      expenseDate: new Date(ms(2026, 12, 5)),
    });
    return season;
  }

  it('bucket dày đặc — tháng không có gì vẫn hiện với số 0', async () => {
    // A sparse series makes a line chart lie about the shape of spending.
    const season = await seasonWithGap();
    const report = await incomeExpenseReport(db, season.id, 'month');

    expect(report.buckets.map(b => b.period)).toEqual([
      '2026-12',
      '2027-01',
      '2027-02',
    ]);
    const january = report.buckets.find(b => b.period === '2027-01')!;
    expect(january.expense).toBe(0);
    expect(january.revenue).toBe(0);
    expect(january.profit).toBe(0);
  });

  it('tổng các bucket bằng tổng chung', async () => {
    const season = await seasonWithGap();
    const report = await incomeExpenseReport(db, season.id, 'month');
    const summed = report.buckets.reduce((s, b) => s + b.profit, 0);
    expect(summed).toBe(report.totals.profit);
  });

  it('mốc theo ngày: 1/12 đến 28/2 là 90 ngày', async () => {
    const season = await seasonWithGap();
    const report = await incomeExpenseReport(db, season.id, 'day');
    expect(report.buckets).toHaveLength(90);
    expect(report.buckets[0]!.period).toBe('2026-12-01');
  });

  it('mốc theo tuần dùng định dạng ISO', async () => {
    const season = await seasonWithGap();
    const report = await incomeExpenseReport(db, season.id, 'week');
    expect(report.buckets.every(b => /^\d{4}-W\d{2}$/.test(b.period))).toBe(true);
  });

  it('mùa vụ rỗng vẫn vẽ được', async () => {
    const season = await createSeason(db, {
      name: 'Vụ mới',
      cropType: 'Ngô',
      startDate: new Date(ms(2027, 3, 1)),
      endDate: new Date(ms(2027, 5, 1)),
    });
    const report = await incomeExpenseReport(db, season.id, 'month');
    expect(report.buckets).toHaveLength(3);
    expect(report.totals.profit).toBe(0);
  });

  it('hoạt động ngoài khung mùa vụ vẫn được tính', async () => {
    // Otherwise the chart total would not match the season summary.
    const season = await createSeason(db, {
      name: 'V',
      cropType: 'Lúa',
      startDate: new Date(ms(2027, 1, 1)),
      endDate: new Date(ms(2027, 1, 31)),
    });
    await createExpense(db, {
      seasonId: season.id,
      category: ExpenseCategory.LABOR,
      amount: 500_000,
      expenseDate: new Date(ms(2027, 3, 15)),
    });

    const report = await incomeExpenseReport(db, season.id, 'month');
    expect(report.totals.expense).toBe(500_000);
    expect(report.buckets.map(b => b.period)).toContain('2027-03');
  });
});

// ═══════════════════════════════════════════════════════════════════════════
//  Biểu đồ 2
// ═══════════════════════════════════════════════════════════════════════════

describe('Biểu đồ 2 — Vật tư tiêu thụ', () => {
  async function consumptionScenario() {
    const season = await createSeason(db, {
      name: 'Vụ Hè Thu',
      cropType: 'Cà chua',
      startDate: new Date(ms(2027, 4, 1)),
    });

    const urea = await createSupply(db, {
      name: 'Đạm Urê',
      category: SupplyCategory.FERTILIZER,
      unit: 'kg',
      unitCost: 12_000,
    });
    const kali = await createSupply(db, {
      name: 'Kali',
      category: SupplyCategory.FERTILIZER,
      unit: 'bao',
      unitCost: 600_000,
    });
    const regent = await createSupply(db, {
      name: 'Regent',
      category: SupplyCategory.PESTICIDE,
      unit: 'chai',
      unitCost: 45_000,
    });

    for (const s of [urea, kali, regent]) {
      await recordStockIn(db, {supplyId: s.id, quantity: 100});
    }

    await createDiaryEntry(db, {
      seasonId: season.id,
      workType: WorkType.FERTILIZING,
      entryDate: new Date(ms(2027, 4, 10)),
      supplyUsages: [
        {supplyId: urea.id, quantity: 50}, //   600,000
        {supplyId: kali.id, quantity: 2}, // 1,200,000
      ],
    });
    await createDiaryEntry(db, {
      seasonId: season.id,
      workType: WorkType.SPRAYING,
      entryDate: new Date(ms(2027, 4, 15)),
      supplyUsages: [{supplyId: regent.id, quantity: 4}], // 180,000
    });

    return {season, urea, kali, regent};
  }

  it('gộp theo nhóm với chi phí đúng', async () => {
    const {season} = await consumptionScenario();
    const report = await supplyConsumptionReport(db, {seasonId: season.id});

    const byKey = new Map(report.items.map(i => [i.key, i]));
    expect(byKey.get('fertilizer')!.totalCost).toBe(1_800_000);
    expect(byKey.get('pesticide')!.totalCost).toBe(180_000);
    expect(report.totalCost).toBe(1_980_000);
  });

  it('trộn đơn vị thì gắn cờ và bỏ trống đơn vị', async () => {
    // Phân bón ở đây có cả kg lẫn bao. Báo "52" cho nhóm đó là con số vô
    // nghĩa, nên biểu đồ phải vẽ theo chi phí.
    const {season} = await consumptionScenario();
    const report = await supplyConsumptionReport(db, {seasonId: season.id});

    const fertilizer = report.items.find(i => i.key === 'fertilizer')!;
    expect(fertilizer.unitMixed).toBe(true);
    expect(fertilizer.unit).toBeNull();

    const pesticide = report.items.find(i => i.key === 'pesticide')!;
    expect(pesticide.unitMixed).toBe(false);
    expect(pesticide.unit).toBe('chai');
  });

  it('tỷ trọng và thứ tự giảm dần', async () => {
    const {season} = await consumptionScenario();
    const report = await supplyConsumptionReport(db, {seasonId: season.id});

    expect(report.items[0]!.key).toBe('fertilizer');
    expect(report.items[0]!.sharePct).toBe(90.9);
    const costs = report.items.map(i => i.totalCost);
    expect(costs).toEqual([...costs].sort((a, b) => b - a));
  });

  it('gộp theo từng vật tư', async () => {
    const {season} = await consumptionScenario();
    const report = await supplyConsumptionReport(db, {
      seasonId: season.id,
      groupBy: 'supply',
    });

    const kali = report.items.find(i => i.label === 'Kali')!;
    expect(kali.totalCost).toBe(1_200_000);
    const urea = report.items.find(i => i.label === 'Đạm Urê')!;
    expect(urea.quantity).toBe(50);
    expect(urea.unit).toBe('kg');
  });

  it('nhập kho KHÔNG phải tiêu thụ', async () => {
    // Tính cả lần mua sẽ nhân đôi mức sử dụng của mọi thứ.
    const {season, urea} = await consumptionScenario();
    await recordStockIn(db, {supplyId: urea.id, quantity: 500, seasonId: season.id});

    const report = await supplyConsumptionReport(db, {seasonId: season.id});
    expect(report.totalCost).toBe(1_980_000);
  });

  it('xuất kho trực tiếp cũng được tính là tiêu thụ', async () => {
    const {season, urea} = await consumptionScenario();
    await recordStockOut(db, {supplyId: urea.id, quantity: 10, seasonId: season.id});

    const report = await supplyConsumptionReport(db, {seasonId: season.id});
    expect(report.totalCost).toBe(1_980_000 + 120_000);
  });

  it('nông hộ chưa có gì thì trả về rỗng', async () => {
    const report = await supplyConsumptionReport(db);
    expect(report.items).toEqual([]);
    expect(report.totalCost).toBe(0);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
//  Biểu đồ 3
// ═══════════════════════════════════════════════════════════════════════════

describe('Biểu đồ 3 — So sánh mùa vụ', () => {
  async function threeSeasons() {
    const specs: [string, number, number][] = [
      ['Vụ 1', 1_000_000, 5_000_000],
      ['Vụ 2', 4_000_000, 2_000_000],
      ['Vụ 3', 2_000_000, 9_000_000],
    ];
    const out: Season[] = [];
    for (const [index, [name, cost, revenue]] of specs.entries()) {
      const season = await createSeason(db, {
        name,
        cropType: 'Lúa',
        startDate: new Date(ms(2026, 1 + index, 1)),
      });
      await createExpense(db, {
        seasonId: season.id,
        category: ExpenseCategory.LABOR,
        amount: cost,
      });
      await createRevenue(db, {seasonId: season.id, amount: revenue});
      out.push(season);
    }
    return out;
  }

  it('lợi nhuận từng mùa vụ', async () => {
    await threeSeasons();
    const report = await seasonComparisonReport(db);
    const byName = new Map(report.seasons.map(s => [s.name, s]));

    expect(byName.get('Vụ 1')!.profit).toBe(4_000_000);
    expect(byName.get('Vụ 2')!.profit).toBe(-2_000_000);
    expect(byName.get('Vụ 3')!.profit).toBe(7_000_000);
  });

  it('xác định mùa vụ tốt nhất và kém nhất', async () => {
    await threeSeasons();
    const report = await seasonComparisonReport(db);
    const byName = new Map(report.seasons.map(s => [s.name, s.seasonId]));

    expect(report.bestSeasonId).toBe(byName.get('Vụ 3'));
    expect(report.worstSeasonId).toBe(byName.get('Vụ 2'));
  });

  it('biên lợi nhuận, kể cả khi lỗ', async () => {
    await threeSeasons();
    const report = await seasonComparisonReport(db);
    const byName = new Map(report.seasons.map(s => [s.name, s]));

    expect(byName.get('Vụ 1')!.marginPct).toBe(80);
    expect(byName.get('Vụ 2')!.marginPct).toBe(-100);
  });

  it('vẽ được với đúng MỘT mùa vụ (Issue #46)', async () => {
    // Một cột, không phải trạng thái lỗi.
    const season = await createSeason(db, {
      name: 'Duy nhất',
      cropType: 'Lúa',
      startDate: new Date(ms(2026, 1, 1)),
    });
    const report = await seasonComparisonReport(db);

    expect(report.seasons).toHaveLength(1);
    expect(report.bestSeasonId).toBe(season.id);
    expect(report.worstSeasonId).toBe(season.id);
  });

  it('mùa vụ chưa có dữ liệu vẫn hiện ở mức 0', async () => {
    // Nông dân so sánh cần thấy vụ họ vừa tạo, không phải nó biến mất.
    await threeSeasons();
    await createSeason(db, {
      name: 'Vừa tạo',
      cropType: 'Ngô',
      startDate: new Date(ms(2026, 6, 1)),
    });

    const report = await seasonComparisonReport(db);
    const fresh = report.seasons.find(s => s.name === 'Vừa tạo')!;
    expect(fresh.profit).toBe(0);
    expect(fresh.marginPct).toBeNull();
  });

  it('không có mùa vụ nào thì trả về rỗng, không lỗi', async () => {
    const report = await seasonComparisonReport(db);
    expect(report.seasons).toEqual([]);
    expect(report.bestSeasonId).toBeNull();
  });

  it('lọc theo trạng thái', async () => {
    const seasons = await threeSeasons();
    await updateSeason(db, seasons[0]!.id, {status: SeasonStatus.CLOSED});

    const report = await seasonComparisonReport(db, {status: SeasonStatus.CLOSED});
    expect(report.seasons).toHaveLength(1);
    expect(report.seasons[0]!.name).toBe('Vụ 1');
  });

  it('giới hạn số lượng', async () => {
    await threeSeasons();
    const report = await seasonComparisonReport(db, {limit: 2});
    expect(report.seasons).toHaveLength(2);
  });
});
