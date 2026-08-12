/**
 * Danh mục vật tư (Issue #24).
 *
 * The rule worth testing hardest: a supply with movement history cannot be
 * deleted, only archived. Tombstoning it would drop the row on every device
 * and leave last season's diary entries showing a blank supply name, and the
 * ledger rows carry the prices past seasons were costed at.
 */

import {Database} from '@nozbe/watermelondb';

import {SupplyCategory} from '../../db/enums';
import type {Supply} from '../../db/models';
import {ValidationError} from '../seasons';
import {recordStockIn, stockLevel} from '../stock';
import {
  archiveSupply,
  createSupply,
  deleteSupply,
  localNameKey,
  movementCount,
  updateSupply,
  validateSupply,
} from '../supplies';
import {createTestDatabase} from './testDatabase';

let db: Database;

beforeEach(() => {
  db = createTestDatabase();
});

function urea() {
  return {
    name: 'Đạm Urê Phú Mỹ',
    category: SupplyCategory.FERTILIZER,
    unit: 'kg',
    unitCost: 12_000,
    lowStockThreshold: 20,
  };
}

// ═══════════════════════════════════════════════════════════════════════════
//  Chuẩn hoá tên
// ═══════════════════════════════════════════════════════════════════════════

describe('localNameKey', () => {
  it('hạ chữ tiếng Việt đầy đủ', () => {
    // The counterpart of the server's normalise_key. PostgreSQL's lower()
    // fails at exactly this under the C collation — see
    // Error_Postgres_Locale_Case_Folding.md.
    expect(localNameKey('Đạm Urê Phú Mỹ')).toBe('đạm urê phú mỹ');
  });

  it('cắt khoảng trắng hai đầu', () => {
    expect(localNameKey('  Kali  ')).toBe('kali');
  });

  it('chuẩn hoá NFC nên tổ hợp dấu không tạo khoá khác', () => {
    const precomposed = 'Phân Kali'.normalize('NFC');
    const decomposed = 'Phân Kali'.normalize('NFD');
    expect(precomposed).not.toBe(decomposed);
    expect(localNameKey(precomposed)).toBe(localNameKey(decomposed));
  });
});

// ═══════════════════════════════════════════════════════════════════════════
//  Kiểm tra hợp lệ
// ═══════════════════════════════════════════════════════════════════════════

describe('validateSupply', () => {
  it('từ chối tên rỗng', () => {
    expect(() => validateSupply({...urea(), name: '  '})).toThrow(ValidationError);
  });

  it('từ chối đơn vị rỗng', () => {
    expect(() => validateSupply({...urea(), unit: ''})).toThrow(ValidationError);
  });

  it('từ chối đơn giá âm', () => {
    expect(() => validateSupply({...urea(), unitCost: -1})).toThrow(ValidationError);
  });

  it('từ chối ngưỡng cảnh báo âm', () => {
    expect(() => validateSupply({...urea(), lowStockThreshold: -5})).toThrow(
      ValidationError,
    );
  });
});

// ═══════════════════════════════════════════════════════════════════════════
//  Tạo và trùng lặp
// ═══════════════════════════════════════════════════════════════════════════

describe('createSupply', () => {
  it('tạo với giá trị đã làm tròn', async () => {
    const supply = await createSupply(db, {...urea(), unitCost: 12_000.456});
    expect(supply.name).toBe('Đạm Urê Phú Mỹ');
    expect(supply.unitCost).toBe(12_000.46);
    expect(supply.isArchived).toBe(false);
  });

  it('chặn trùng tên bất kể hoa thường', async () => {
    await createSupply(db, urea());
    await expect(createSupply(db, {...urea(), name: 'đạm urê phú mỹ'})).rejects.toThrow(
      'đã có trong danh mục',
    );
  });

  it('chặn trùng khi chỉ khác khoảng trắng', async () => {
    await createSupply(db, urea());
    await expect(
      createSupply(db, {...urea(), name: '  Đạm Urê Phú Mỹ  '}),
    ).rejects.toThrow(ValidationError);
  });

  it('cùng tên khác đơn vị là hai dòng hợp lệ', async () => {
    // 'Đạm Urê' theo kg và theo bao là hai mục tồn kho thật.
    await createSupply(db, urea());
    const byBag = await createSupply(db, {...urea(), unit: 'bao'});
    expect(byBag.id).toBeTruthy();
    expect(await db.get<Supply>('supplies').query().fetchCount()).toBe(2);
  });
});

describe('updateSupply', () => {
  it('sửa từng phần', async () => {
    const supply = await createSupply(db, {...urea(), note: 'ghi chú'});
    await updateSupply(db, supply.id, {unitCost: 13_500});

    const fresh = await db.get<Supply>('supplies').find(supply.id);
    expect(fresh.unitCost).toBe(13_500);
    expect(fresh.note).toBe('ghi chú');
    expect(fresh.name).toBe('Đạm Urê Phú Mỹ');
  });

  it('đổi giá KHÔNG viết lại lịch sử giao dịch', async () => {
    // Phân bón mua tháng 3 giá 12.000đ/kg phải giữ nguyên giá đó.
    const supply = await createSupply(db, urea());
    await recordStockIn(db, {supplyId: supply.id, quantity: 10});

    await updateSupply(db, supply.id, {unitCost: 99_000});

    const txns = await db.get('stock_transactions').query().fetch();
    expect((txns[0] as unknown as {unitCost: number}).unitCost).toBe(12_000);
    expect((txns[0] as unknown as {totalCost: number}).totalCost).toBe(120_000);
  });

  it('đổi tên thành trùng với vật tư khác thì bị chặn', async () => {
    await createSupply(db, urea());
    const kali = await createSupply(db, {
      ...urea(),
      name: 'Kali Clorua',
    });
    await expect(
      updateSupply(db, kali.id, {name: 'đạm urê phú mỹ'}),
    ).rejects.toThrow('đã có trong danh mục');
  });

  it('giữ nguyên tên của chính nó thì không báo trùng', async () => {
    const supply = await createSupply(db, urea());
    await expect(
      updateSupply(db, supply.id, {name: 'Đạm Urê Phú Mỹ', unitCost: 1}),
    ).resolves.toBeTruthy();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
//  Xoá và lưu trữ
// ═══════════════════════════════════════════════════════════════════════════

describe('Xoá và lưu trữ', () => {
  it('xoá được khi chưa có giao dịch', async () => {
    const supply = await createSupply(db, urea());
    await deleteSupply(db, supply.id);
    expect(await db.get<Supply>('supplies').query().fetchCount()).toBe(0);
  });

  it('KHÔNG xoá được khi đã có giao dịch kho', async () => {
    const supply = await createSupply(db, urea());
    await recordStockIn(db, {supplyId: supply.id, quantity: 10});

    await expect(deleteSupply(db, supply.id)).rejects.toThrow('không thể xoá');
    expect(await db.get<Supply>('supplies').query().fetchCount()).toBe(1);
  });

  it('lưu trữ ẩn khỏi danh sách nhưng giữ dòng và sổ cái', async () => {
    const supply = await createSupply(db, urea());
    await recordStockIn(db, {supplyId: supply.id, quantity: 10});

    await archiveSupply(db, supply.id);

    const fresh = await db.get<Supply>('supplies').find(supply.id);
    expect(fresh.isArchived).toBe(true);
    // Dòng vẫn còn, tồn kho vẫn tính được, tên vẫn hiển thị được trên nhật ký cũ.
    expect(await stockLevel(db, supply.id)).toBe(10);
    expect(await movementCount(db, supply.id)).toBe(1);
  });

  it('bỏ lưu trữ đưa vật tư trở lại', async () => {
    const supply = await createSupply(db, urea());
    await archiveSupply(db, supply.id);
    await archiveSupply(db, supply.id, false);

    const fresh = await db.get<Supply>('supplies').find(supply.id);
    expect(fresh.isArchived).toBe(false);
  });
});
