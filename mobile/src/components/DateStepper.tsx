/**
 * Chọn ngày, không dùng picker native.
 *
 * Deliberately not @react-native-community/datetimepicker. Two reasons:
 *
 *   1. It is a native module needing a link step, and the value it adds here
 *      is small — in a farming diary the entry is for today in the
 *      overwhelming majority of cases, and for yesterday in most of the rest.
 *   2. A calendar grid means precise taps. This is used standing in a field
 *      with wet hands; two big chips and two big arrows are faster and far
 *      more reliable than hitting a 30x30 cell.
 *
 * The arrows stay available for the genuine "I forgot to log Tuesday" case,
 * and future dates are refused because a diary records what happened.
 */

import React from 'react';
import {StyleSheet, Text, TouchableOpacity, View} from 'react-native';

import {colors, MIN_TOUCH_TARGET, radius, spacing, typography} from '../theme';
import {formatDate, localDayIndex, MS_PER_DAY, startOfLocalDay} from '../utils/date';

export interface DateStepperProps {
  value: Date;
  onChange: (value: Date) => void;
  /** Refuse dates after today. A diary records what happened. */
  maxToday?: boolean;
}

export default function DateStepper({value, onChange, maxToday = true}: DateStepperProps) {
  const today = localDayIndex(Date.now());
  const selected = localDayIndex(value.getTime());

  const isToday = selected === today;
  const isYesterday = selected === today - 1;
  const canGoForward = !maxToday || selected < today;

  const shift = (days: number) => {
    const next = localDayIndex(value.getTime()) + days;
    if (maxToday && next > today) {
      return;
    }
    onChange(new Date(next * MS_PER_DAY + 12 * 3600 * 1000));
  };

  const jumpTo = (dayIndex: number) =>
    onChange(new Date(dayIndex * MS_PER_DAY + 12 * 3600 * 1000));

  return (
    <View>
      <View style={styles.quickRow}>
        <TouchableOpacity
          style={[styles.chip, isToday && styles.chipActive]}
          onPress={() => jumpTo(today)}>
          <Text style={[styles.chipText, isToday && styles.chipTextActive]}>Hôm nay</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.chip, isYesterday && styles.chipActive]}
          onPress={() => jumpTo(today - 1)}>
          <Text style={[styles.chipText, isYesterday && styles.chipTextActive]}>
            Hôm qua
          </Text>
        </TouchableOpacity>
      </View>

      <View style={styles.stepper}>
        <TouchableOpacity
          style={styles.arrow}
          onPress={() => shift(-1)}
          accessibilityRole="button"
          accessibilityLabel="Lùi một ngày">
          <Text style={styles.arrowText}>‹</Text>
        </TouchableOpacity>

        <Text style={styles.date}>{formatDate(startOfLocalDay(value))}</Text>

        <TouchableOpacity
          style={[styles.arrow, !canGoForward && styles.arrowDisabled]}
          onPress={() => shift(1)}
          disabled={!canGoForward}
          accessibilityRole="button"
          accessibilityLabel="Tiến một ngày">
          <Text style={[styles.arrowText, !canGoForward && styles.arrowTextDisabled]}>›</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  quickRow: {flexDirection: 'row', marginBottom: spacing.sm},
  chip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    marginRight: spacing.xs,
  },
  chipActive: {backgroundColor: colors.primary, borderColor: colors.primary},
  chipText: {...typography.caption, color: colors.textSecondary},
  chipTextActive: {color: colors.textOnPrimary, fontWeight: '600'},

  stepper: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    minHeight: MIN_TOUCH_TARGET,
  },
  arrow: {
    width: MIN_TOUCH_TARGET + 8,
    minHeight: MIN_TOUCH_TARGET,
    alignItems: 'center',
    justifyContent: 'center',
  },
  arrowDisabled: {opacity: 0.3},
  arrowText: {fontSize: 30, color: colors.primary, lineHeight: 34},
  arrowTextDisabled: {color: colors.textDisabled},
  date: {...typography.heading, color: colors.text},
});
