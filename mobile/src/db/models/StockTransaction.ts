import {Model, type Relation} from '@nozbe/watermelondb';
import type {Associations} from '@nozbe/watermelondb/Model';
import {date, field, readonly, relation, text} from '@nozbe/watermelondb/decorators';

import {TxnType} from '../enums';
import type DiaryEntry from './DiaryEntry';
import type Season from './Season';
import type Supply from './Supply';

/** One movement in the append-only inventory ledger. */
export default class StockTransaction extends Model {
  static table = 'stock_transactions';

  static associations: Associations = {
    supplies: {type: 'belongs_to', key: 'supply_id'},
    seasons: {type: 'belongs_to', key: 'season_id'},
    diary_entries: {type: 'belongs_to', key: 'diary_entry_id'},
  };

  @text('supply_id') supplyId!: string;
  @text('season_id') seasonId!: string | null;
  /** Set ⟺ this movement was caused by a diary entry. */
  @text('diary_entry_id') diaryEntryId!: string | null;
  @text('txn_type') txnType!: TxnType;
  /** Always positive for in/out; `adjust` carries a signed delta. */
  @field('quantity') quantity!: number;
  /** Snapshot at movement time, never a live join to the supply's price. */
  @field('unit_cost') unitCost!: number;
  @field('total_cost') totalCost!: number;
  @date('txn_date') txnDate!: Date;
  @text('note') note!: string | null;

  @readonly @date('created_at') createdAt!: Date;
  @date('updated_at') updatedAt!: Date;

  @relation('supplies', 'supply_id') supply!: Relation<Supply>;
  @relation('seasons', 'season_id') season!: Relation<Season>;
  @relation('diary_entries', 'diary_entry_id') diaryEntry!: Relation<DiaryEntry>;

  /** Effect on inventory: positive adds, negative removes. */
  get signedQuantity(): number {
    return this.txnType === TxnType.OUT ? -this.quantity : this.quantity;
  }
}
