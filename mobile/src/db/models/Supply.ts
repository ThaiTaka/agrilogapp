import {Model, type Query} from '@nozbe/watermelondb';
import type {Associations} from '@nozbe/watermelondb/Model';
import {children, date, field, readonly, text} from '@nozbe/watermelondb/decorators';

import type {SupplyCategory} from '../enums';
import type StockTransaction from './StockTransaction';

/**
 * Vật tư — an agricultural input the household keeps in stock.
 *
 * NOTE the field that is deliberately absent: there is no `currentStock`.
 * On-hand quantity is never stored, only ever derived from the ledger
 * (see services/stock.ts). A cached counter decremented independently by two
 * offline devices is undetectably wrong after sync — that is the central
 * data-modelling decision of this module (D1).
 */
export default class Supply extends Model {
  static table = 'supplies';

  static associations: Associations = {
    stock_transactions: {type: 'has_many', foreignKey: 'supply_id'},
  };

  @text('name') name!: string;
  @text('category') category!: SupplyCategory;
  @text('unit') unit!: string;
  /** VND per `unit`. Snapshotted onto each movement at the time it happens. */
  @field('unit_cost') unitCost!: number;
  @field('low_stock_threshold') lowStockThreshold!: number;
  /**
   * Hidden from the picker but NOT deleted. A supply with movement history can
   * only be archived: deleting it would drop the row on every device and leave
   * last season's diary entries showing a blank supply name.
   */
  @field('is_archived') isArchived!: boolean;
  @text('note') note!: string | null;

  @readonly @date('created_at') createdAt!: Date;
  @date('updated_at') updatedAt!: Date;

  @children('stock_transactions') transactions!: Query<StockTransaction>;
}
