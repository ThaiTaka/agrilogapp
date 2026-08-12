import {Model, type Query, type Relation} from '@nozbe/watermelondb';
import type {Associations} from '@nozbe/watermelondb/Model';
import {children, date, field, readonly, relation, text} from '@nozbe/watermelondb/decorators';

import type {WorkType} from '../enums';
import type Season from './Season';
import type StockTransaction from './StockTransaction';

/**
 * Nhật ký canh tác — one logged piece of field work.
 *
 * Supply consumption is deliberately NOT stored here. It lives in
 * `stock_transactions` rows pointing back via `diary_entry_id`. The form
 * presents them as one screen; the data model keeps them as a parent plus
 * ledger children, which is what makes the stock-restore operation
 * well defined (Issue #26).
 */
export default class DiaryEntry extends Model {
  static table = 'diary_entries';

  static associations: Associations = {
    seasons: {type: 'belongs_to', key: 'season_id'},
    stock_transactions: {type: 'has_many', foreignKey: 'diary_entry_id'},
  };

  @text('season_id') seasonId!: string;
  @text('work_type') workType!: WorkType;
  @date('entry_date') entryDate!: Date;
  @text('title') title!: string | null;
  @text('note') note!: string | null;
  @text('weather') weather!: string | null;
  @field('labor_hours') laborHours!: number | null;

  @readonly @date('created_at') createdAt!: Date;
  @date('updated_at') updatedAt!: Date;

  @relation('seasons', 'season_id') season!: Relation<Season>;
  @children('stock_transactions') usages!: Query<StockTransaction>;
}
