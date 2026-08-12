/**
 * Khai báo vật tư đã dùng trong một nhật ký (Issue #22).
 *
 * This is where the app's central convenience happens: the farmer records
 * "2 chai Regent" once, and the stock-out and the expense both appear by
 * themselves. So the editor shows the cost as it is typed — seeing
 * "90.000 ₫" update live is what makes the automatic half believable.
 *
 * Only one row per supply is allowed, matching the reconciliation rule on
 * both sides: edits are matched by supply, so two rows for one supply would
 * make "which row did they change?" unanswerable.
 */

import React, {useCallback, useMemo} from 'react';
import {StyleSheet, Text, TextInput, TouchableOpacity, View} from 'react-native';

import type {Supply} from '../db/models';
import {colors, MIN_TOUCH_TARGET, radius, spacing, typography} from '../theme';
import {formatMoney, lineTotal, parseNumberInput} from '../utils/numeric';

export interface UsageRow {
  supplyId: string;
  /** Kept as typed text, not a number: '12,' is a valid intermediate state. */
  quantityText: string;
}

export interface SupplyUsageEditorProps {
  supplies: Supply[];
  rows: UsageRow[];
  onChange: (rows: UsageRow[]) => void;
  /** supplyId → on-hand, so the farmer can see what is left before typing. */
  stockLevels?: Map<string, number>;
}

export default function SupplyUsageEditor({
  supplies,
  rows,
  onChange,
  stockLevels,
}: SupplyUsageEditorProps) {
  const byId = useMemo(() => new Map(supplies.map(s => [s.id, s])), [supplies]);
  const usedIds = useMemo(() => new Set(rows.map(r => r.supplyId)), [rows]);
  const available = useMemo(
    () => supplies.filter(s => !s.isArchived && !usedIds.has(s.id)),
    [supplies, usedIds],
  );

  const total = useMemo(
    () =>
      rows.reduce((sum, row) => {
        const supply = byId.get(row.supplyId);
        const qty = parseNumberInput(row.quantityText);
        return supply && qty ? sum + lineTotal(qty, supply.unitCost) : sum;
      }, 0),
    [rows, byId],
  );

  const addRow = useCallback(
    (supplyId: string) => onChange([...rows, {supplyId, quantityText: ''}]),
    [rows, onChange],
  );

  const setQuantity = useCallback(
    (supplyId: string, quantityText: string) =>
      onChange(rows.map(r => (r.supplyId === supplyId ? {...r, quantityText} : r))),
    [rows, onChange],
  );

  const removeRow = useCallback(
    (supplyId: string) => onChange(rows.filter(r => r.supplyId !== supplyId)),
    [rows, onChange],
  );

  if (supplies.length === 0) {
    return (
      <View style={styles.notice}>
        <Text style={styles.noticeText}>
          Chưa có vật tư nào trong danh mục. Thêm vật tư ở tab Vật tư để ghi được
          lượng đã dùng.
        </Text>
      </View>
    );
  }

  return (
    <View>
      {rows.map(row => {
        const supply = byId.get(row.supplyId);
        if (!supply) {
          return null;
        }
        const qty = parseNumberInput(row.quantityText);
        const cost = qty ? lineTotal(qty, supply.unitCost) : 0;
        const onHand = stockLevels?.get(supply.id);
        // Not an error — just information. Going negative is allowed (I2);
        // blocking would force the farmer to abandon the entry entirely.
        const wouldGoNegative = onHand !== undefined && qty !== null && qty > onHand;

        return (
          <View key={row.supplyId} style={styles.row}>
            <View style={styles.rowHeader}>
              <Text style={styles.rowName} numberOfLines={1}>
                {supply.name}
              </Text>
              <TouchableOpacity
                onPress={() => removeRow(row.supplyId)}
                accessibilityRole="button"
                accessibilityLabel={`Bỏ ${supply.name}`}
                hitSlop={{top: 12, bottom: 12, left: 12, right: 12}}>
                <Text style={styles.remove}>✕</Text>
              </TouchableOpacity>
            </View>

            <View style={styles.rowBody}>
              <TextInput
                style={styles.qtyInput}
                value={row.quantityText}
                onChangeText={t => setQuantity(row.supplyId, t)}
                keyboardType="decimal-pad"
                placeholder="0"
                placeholderTextColor={colors.textDisabled}
              />
              <Text style={styles.unit}>{supply.unit}</Text>
              <Text style={styles.cost}>{formatMoney(cost)}</Text>
            </View>

            {onHand !== undefined && (
              <Text style={[styles.stock, wouldGoNegative && styles.stockWarn]}>
                {wouldGoNegative
                  ? `Tồn kho chỉ còn ${onHand} ${supply.unit} — vẫn ghi được, nhớ bổ sung phiếu nhập`
                  : `Còn ${onHand} ${supply.unit}`}
              </Text>
            )}
          </View>
        );
      })}

      {available.length > 0 && (
        <View style={styles.picker}>
          <Text style={styles.pickerLabel}>Thêm vật tư</Text>
          <View style={styles.chips}>
            {available.map(supply => (
              <TouchableOpacity
                key={supply.id}
                style={styles.chip}
                onPress={() => addRow(supply.id)}>
                <Text style={styles.chipText}>+ {supply.name}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      )}

      {rows.length > 0 && (
        <View style={styles.totalRow}>
          <Text style={styles.totalLabel}>Chi phí vật tư</Text>
          <Text style={styles.totalValue}>{formatMoney(total)}</Text>
        </View>
      )}

      {rows.length > 0 && (
        <Text style={styles.hint}>
          Khoản chi này được tạo tự động khi lưu — không cần nhập lại ở tab Thu chi.
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  notice: {
    backgroundColor: '#FFF8E1',
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: '#FFE082',
  },
  noticeText: {...typography.caption, color: colors.text, lineHeight: 18},

  row: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.sm,
    marginBottom: spacing.sm,
  },
  rowHeader: {flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between'},
  rowName: {...typography.label, color: colors.text, flex: 1},
  remove: {fontSize: 18, color: colors.textSecondary, paddingHorizontal: spacing.xs},
  rowBody: {flexDirection: 'row', alignItems: 'center', marginTop: spacing.xs},
  qtyInput: {
    ...typography.body,
    minHeight: MIN_TOUCH_TARGET,
    width: 96,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    color: colors.text,
    textAlign: 'right',
  },
  unit: {...typography.body, color: colors.textSecondary, marginLeft: spacing.sm, flex: 1},
  cost: {...typography.label, color: colors.primary},
  stock: {...typography.caption, color: colors.textSecondary, marginTop: spacing.xs},
  stockWarn: {color: colors.warning},

  picker: {marginTop: spacing.xs},
  pickerLabel: {...typography.caption, color: colors.textSecondary, marginBottom: spacing.xs},
  chips: {flexDirection: 'row', flexWrap: 'wrap'},
  chip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.primaryLight,
    backgroundColor: '#F1F8E9',
    marginRight: spacing.xs,
    marginBottom: spacing.xs,
  },
  chipText: {...typography.caption, color: colors.primaryDark, fontWeight: '600'},

  totalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  totalLabel: {...typography.label, color: colors.textSecondary},
  totalValue: {...typography.heading, color: colors.primary},
  hint: {...typography.caption, color: colors.textSecondary, marginTop: spacing.xs},
});
