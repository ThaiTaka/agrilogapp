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

  accent: '#F57C00', // cam đất
  danger: '#C62828',
  warning: '#EF6C00',
  success: '#2E7D32',
  info: '#0277BD',

  background: '#F5F5F5',
  surface: '#FFFFFF',
  border: '#E0E0E0',

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
  md: 16,
  lg: 24,
  xl: 32,
} as const;

export const radius = {
  sm: 4,
  md: 8,
  lg: 16,
  pill: 999,
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
