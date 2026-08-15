/**
 * Design tokens.
 *
 * Sized for the actual use case: a farmer standing in a field, in sunlight,
 * possibly with wet or muddy hands. That drives three choices that look
 * excessive on a desktop mockup and are not:
 *   - minimum touch target 48dp (Android accessibility floor, not a nicety)
 *   - body text 16sp, never smaller
 *   - high contrast throughout — mid-greys vanish in direct sun
 */

export const colors = {
  primary: '#2E7D32', // xanh lá đậm — cây trồng
  primaryDark: '#1B5E20',
  primaryLight: '#A5D6A7',
  /** Nền nhạt cho vùng được nhấn mạnh — đủ nhạt để chữ đen vẫn đọc rõ. */
  primarySoft: '#E8F5E9',

  accent: '#F57C00', // cam đất
  danger: '#C62828',
  warning: '#EF6C00',
  success: '#2E7D32',
  info: '#0277BD',

  // Nền ngả xanh rất nhẹ thay vì xám trung tính: thẻ trắng nổi hẳn lên, và
  // màn hình bớt cảm giác "trang giấy trắng" mà vẫn không đụng tới độ tương
  // phản của chữ.
  background: '#F3F7F3',
  surface: '#FFFFFF',
  border: '#E3EAE3',

  text: '#1A1A1A',
  textSecondary: '#5A5A5A',
  textDisabled: '#9E9E9E',
  textOnPrimary: '#FFFFFF',

  // Sync states — mirrored in the status bar and per-row badges
  synced: '#2E7D32',
  pending: '#F57C00',
  offline: '#757575',
  syncError: '#C62828',
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  // Bậc trung gian giữa 8 và 16. Khoảng cách giữa các thẻ trong danh sách rơi
  // đúng vào đây: 8 thì dính nhau, 16 thì mỗi màn hình bớt mất một thẻ — đáng
  // kể trên điện thoại nhỏ, vốn là máy phần lớn bà con đang dùng.
  ms: 12,
  md: 16,
  lg: 24,
  xl: 32,
} as const;

export const radius = {
  sm: 4,
  md: 12,
  lg: 18,
  pill: 999,
} as const;

/**
 * Đổ bóng.
 *
 * Trên Android chỉ `elevation` có tác dụng; các thuộc tính `shadow*` là phần
 * của iOS. Khai cả hai ở một chỗ để hai nền tảng không lệch nhau theo thời
 * gian.
 *
 * Cố ý nhẹ tay: bóng ở đây để tách thẻ khỏi nền, không phải để trang trí. Bóng
 * đậm trên màn hình ngoài nắng chỉ thành một vệt xám làm bẩn giao diện.
 */
export const shadows = {
  /** Thẻ trong danh sách. */
  card: {
    elevation: 2,
    shadowColor: '#14301A',
    shadowOffset: {width: 0, height: 2},
    shadowOpacity: 0.08,
    shadowRadius: 6,
  },
  /** Nút nổi (FAB) — cần tách khỏi nội dung cuộn bên dưới nó. */
  floating: {
    elevation: 6,
    shadowColor: '#14301A',
    shadowOffset: {width: 0, height: 4},
    shadowOpacity: 0.22,
    shadowRadius: 10,
  },
} as const;

export const typography = {
  title: {fontSize: 22, fontWeight: '700'},
  heading: {fontSize: 18, fontWeight: '600'},
  body: {fontSize: 16, fontWeight: '400'},
  label: {fontSize: 14, fontWeight: '600'},
  caption: {fontSize: 13, fontWeight: '400'},
} as const;

/** Android accessibility minimum. Not negotiable for muddy hands. */
export const MIN_TOUCH_TARGET = 48;
