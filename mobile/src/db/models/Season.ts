import {Model, Q, type Query} from '@nozbe/watermelondb';
import type {Associations} from '@nozbe/watermelondb/Model';
import {children, date, field, lazy, readonly, text} from '@nozbe/watermelondb/decorators';

import type {SeasonStatus} from '../enums';
import type DiaryEntry from './DiaryEntry';
import type Expense from './Expense';
import type Revenue from './Revenue';
import type StockTransaction from './StockTransaction';

/** Mùa vụ — the organising unit for every other record. */
export default class Season extends Model {
  static table = 'seasons';

  static associations: Associations = {
    diary_entries: {type: 'has_many', foreignKey: 'season_id'},
    stock_transactions: {type: 'has_many', foreignKey: 'season_id'},
    expenses: {type: 'has_many', foreignKey: 'season_id'},
    revenues: {type: 'has_many', foreignKey: 'season_id'},
  };

  @text('name') name!: string;
  @text('crop_type') cropType!: string;
  @field('area_size') areaSize!: number | null;
  @text('area_unit') areaUnit!: string;
  @date('start_date') startDate!: Date;
  /** null = the season is still running; the farmer has not decided when it ends. */
  @date('end_date') endDate!: Date | null;
  @text('status') status!: SeasonStatus;
  @text('note') note!: string | null;

  @readonly @date('created_at') createdAt!: Date;
  @date('updated_at') updatedAt!: Date;

  @children('diary_entries') diaryEntries!: Query<DiaryEntry>;
  @children('stock_transactions') stockTransactions!: Query<StockTransaction>;
  @children('expenses') expenses!: Query<Expense>;
  @children('revenues') revenues!: Query<Revenue>;

  /** Live consumption for this season — drives the supply-consumption chart. */
  @lazy consumption = this.stockTransactions.extend(Q.where('txn_type', 'out'));
}
