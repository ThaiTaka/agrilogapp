import {Model, type Relation} from '@nozbe/watermelondb';
import type {Associations} from '@nozbe/watermelondb/Model';
import {date, field, readonly, relation, text} from '@nozbe/watermelondb/decorators';

import type Season from './Season';

/**
 * Khoản thu — income from selling harvest.
 *
 * `amount` is authoritative and always stored, even when quantity and
 * unitPrice are present. The form pre-fills it from the product but lets the
 * farmer override: real sales get rounded down, discounted for moisture, or
 * partly paid. Deriving the total on read would silently discard the number
 * they were actually paid.
 */
export default class Revenue extends Model {
  static table = 'revenues';

  static associations: Associations = {
    seasons: {type: 'belongs_to', key: 'season_id'},
  };

  @text('season_id') seasonId!: string;
  @field('quantity') quantity!: number | null;
  @text('unit') unit!: string | null;
  @field('unit_price') unitPrice!: number | null;
  @field('amount') amount!: number;
  @date('revenue_date') revenueDate!: Date;
  @text('buyer') buyer!: string | null;
  @text('description') description!: string | null;

  @readonly @date('created_at') createdAt!: Date;
  @date('updated_at') updatedAt!: Date;

  @relation('seasons', 'season_id') season!: Relation<Season>;
}
