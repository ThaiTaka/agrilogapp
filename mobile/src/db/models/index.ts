import DiaryEntry from './DiaryEntry';
import Expense from './Expense';
import Revenue from './Revenue';
import Season from './Season';
import StockTransaction from './StockTransaction';
import Supply from './Supply';

export {DiaryEntry, Expense, Revenue, Season, StockTransaction, Supply};

/**
 * Registered with the Database in dependency order — the same order as
 * SYNC_TABLES in schema.ts and SYNC_TABLE_ORDER on the backend.
 */
export const modelClasses = [
  Season,
  Supply,
  DiaryEntry,
  StockTransaction,
  Expense,
  Revenue,
];
