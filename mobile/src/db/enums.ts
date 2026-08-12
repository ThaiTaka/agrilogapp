/**
 * Canonical enumerations — mirrors backend/app/models/enums.py.
 *
 * The values are the contract; the labels are what the farmer reads. Both
 * live here so the two sides cannot disagree about what `land_prep` is
 * called. A backend test asserts every CHECK constraint in PostgreSQL matches
 * the Python tuples, and the values below must match those in turn.
 */

export const WorkType = {
  LAND_PREP: 'land_prep',
  SOWING: 'sowing',
  FERTILIZING: 'fertilizing',
  SPRAYING: 'spraying',
  WATERING: 'watering',
  WEEDING: 'weeding',
  HARVESTING: 'harvesting',
  OTHER: 'other',
} as const;
export type WorkType = (typeof WorkType)[keyof typeof WorkType];

export const SupplyCategory = {
  FERTILIZER: 'fertilizer',
  PESTICIDE: 'pesticide',
  SEED: 'seed',
  FUEL: 'fuel',
  TOOL: 'tool',
  OTHER: 'other',
} as const;
export type SupplyCategory = (typeof SupplyCategory)[keyof typeof SupplyCategory];

export const TxnType = {
  IN: 'in',
  OUT: 'out',
  ADJUST: 'adjust',
} as const;
export type TxnType = (typeof TxnType)[keyof typeof TxnType];

export const ExpenseCategory = {
  SUPPLY: 'supply',
  LABOR: 'labor',
  MACHINERY: 'machinery',
  TRANSPORT: 'transport',
  LAND_RENT: 'land_rent',
  IRRIGATION: 'irrigation',
  OTHER: 'other',
} as const;
export type ExpenseCategory = (typeof ExpenseCategory)[keyof typeof ExpenseCategory];

export const ExpenseSource = {
  MANUAL: 'manual',
  DIARY_AUTO: 'diary_auto',
} as const;
export type ExpenseSource = (typeof ExpenseSource)[keyof typeof ExpenseSource];

export const SeasonStatus = {
  PLANNING: 'planning',
  ACTIVE: 'active',
  HARVESTED: 'harvested',
  CLOSED: 'closed',
} as const;
export type SeasonStatus = (typeof SeasonStatus)[keyof typeof SeasonStatus];

// ─── Nhãn tiếng Việt ────────────────────────────────────────────────────────

export const WORK_TYPE_LABELS: Record<WorkType, string> = {
  land_prep: 'Làm đất',
  sowing: 'Gieo/Trồng',
  fertilizing: 'Bón phân',
  spraying: 'Phun thuốc',
  watering: 'Tưới nước',
  weeding: 'Làm cỏ',
  harvesting: 'Thu hoạch',
  other: 'Khác',
};

export const SUPPLY_CATEGORY_LABELS: Record<SupplyCategory, string> = {
  fertilizer: 'Phân bón',
  pesticide: 'Thuốc BVTV',
  seed: 'Giống',
  fuel: 'Nhiên liệu',
  tool: 'Dụng cụ',
  other: 'Khác',
};

export const TXN_TYPE_LABELS: Record<TxnType, string> = {
  in: 'Nhập kho',
  out: 'Xuất kho',
  adjust: 'Điều chỉnh',
};

export const EXPENSE_CATEGORY_LABELS: Record<ExpenseCategory, string> = {
  supply: 'Vật tư',
  labor: 'Nhân công',
  machinery: 'Máy móc',
  transport: 'Vận chuyển',
  land_rent: 'Thuê đất',
  irrigation: 'Thủy lợi',
  other: 'Khác',
};

export const SEASON_STATUS_LABELS: Record<SeasonStatus, string> = {
  planning: 'Chuẩn bị',
  active: 'Đang canh tác',
  harvested: 'Đã thu hoạch',
  closed: 'Đã kết thúc',
};

export const AREA_UNITS = ['sao', 'ha', 'm2', 'công', 'mẫu'] as const;
export const SUPPLY_UNITS = ['kg', 'g', 'tấn', 'L', 'ml', 'bao', 'chai', 'gói', 'cái', 'bình'] as const;
export const REVENUE_UNITS = ['kg', 'tạ', 'tấn', 'bao', 'thùng', 'quả', 'bó'] as const;
export const WEATHER_VALUES = ['sunny', 'cloudy', 'rain', 'storm', 'windy'] as const;

export const WEATHER_LABELS: Record<string, string> = {
  sunny: 'Nắng',
  cloudy: 'Nhiều mây',
  rain: 'Mưa',
  storm: 'Giông bão',
  windy: 'Gió mạnh',
};
