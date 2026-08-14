/**
 * Ghi / sửa khoản thu (Issue #28).
 *
 * The total is pre-filled from sản lượng × đơn giá but stays editable, and
 * the edited value wins. Real sales get rounded down, discounted for
 * moisture, or partly paid — deriving the total on save would silently
 * discard the number the farmer was actually handed.
 */

import React, {useCallback, useEffect, useState} from 'react';
import {
  Alert,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';

import DateStepper from '../../components/DateStepper';
import FormScaffold from '../../components/FormScaffold';
import {database} from '../../db';
import {REVENUE_UNITS} from '../../db/enums';
import type {Revenue} from '../../db/models';
import {createRevenue, deleteRevenue, updateRevenue} from '../../services/finance';
import {ValidationError} from '../../services/seasons';
import {colors, MIN_TOUCH_TARGET, radius, spacing, typography} from '../../theme';
import {formatMoney, parseNumberInput, quantizeMoney} from '../../utils/numeric';

export interface RevenueFormProps {
  seasonId: string;
  revenue?: Revenue;
  onSaved?: () => void;
  onDeleted?: () => void;
  onCancel?: () => void;
}

export default function RevenueFormScreen({
  seasonId,
  revenue,
  onSaved,
  onDeleted,
  onCancel,
}: RevenueFormProps) {
  const isEdit = Boolean(revenue);

  const [quantityText, setQuantityText] = useState(
    revenue?.quantity != null ? String(revenue.quantity).replace('.', ',') : '',
  );
  const [unit, setUnit] = useState(revenue?.unit ?? 'kg');
  const [unitPriceText, setUnitPriceText] = useState(
    revenue?.unitPrice != null ? String(revenue.unitPrice) : '',
  );
  const [amountText, setAmountText] = useState(
    revenue?.amount != null ? String(revenue.amount) : '',
  );
  /**
   * Once the farmer edits the total by hand, stop overwriting it. Without
   * this flag, typing a discounted total and then correcting the weight would
   * silently wipe the discount.
   */
  const [amountTouched, setAmountTouched] = useState(isEdit);
  const [revenueDate, setRevenueDate] = useState(revenue?.revenueDate ?? new Date());
  const [buyer, setBuyer] = useState(revenue?.buyer ?? '');
  const [description, setDescription] = useState(revenue?.description ?? '');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const quantity = parseNumberInput(quantityText);
  const unitPrice = parseNumberInput(unitPriceText);
  const amount = parseNumberInput(amountText);

  // Pre-fill only; never override a hand-typed total.
  useEffect(() => {
    if (amountTouched || quantity === null || unitPrice === null) {
      return;
    }
    setAmountText(String(quantizeMoney(quantity * unitPrice)));
  }, [quantity, unitPrice, amountTouched]);

  const canSave = amount !== null && amount >= 0 && !busy;

  const onSave = useCallback(async () => {
    if (!canSave) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const input = {
        seasonId,
        quantity,
        unit: quantity !== null ? unit : null,
        unitPrice,
        amount,
        revenueDate,
        buyer: buyer.trim() || null,
        description: description.trim() || null,
      };
      if (revenue) {
        await updateRevenue(database, revenue.id, input);
      } else {
        await createRevenue(database, input);
      }
      onSaved?.();
    } catch (e) {
      setError(
        e instanceof ValidationError ? e.message : 'Không lưu được. Vui lòng thử lại.',
      );
    } finally {
      setBusy(false);
    }
  }, [
    canSave,
    seasonId,
    quantity,
    unit,
    unitPrice,
    amount,
    revenueDate,
    buyer,
    description,
    revenue,
    onSaved,
  ]);

  const onDelete = useCallback(() => {
    if (!revenue) {
      return;
    }
    Alert.alert('Xoá khoản thu?', formatMoney(revenue.amount), [
      {text: 'Huỷ', style: 'cancel'},
      {
        text: 'Xoá',
        style: 'destructive',
        onPress: async () => {
          await deleteRevenue(database, revenue.id);
          onDeleted?.();
        },
      },
    ]);
  }, [revenue, onDeleted]);

  const derived =
    quantity !== null && unitPrice !== null ? quantizeMoney(quantity * unitPrice) : null;
  const overridden = derived !== null && amount !== null && amount !== derived;

  return (
    <FormScaffold contentContainerStyle={styles.container}>
        <Text style={styles.label}>Sản lượng bán</Text>
        <View style={styles.row}>
          <TextInput
            style={[styles.input, styles.rowInput]}
            value={quantityText}
            onChangeText={setQuantityText}
            keyboardType="decimal-pad"
            placeholder="1250"
            placeholderTextColor={colors.textDisabled}
          />
          <View style={styles.chips}>
            {REVENUE_UNITS.map(value => (
              <TouchableOpacity
                key={value}
                style={[styles.chip, unit === value && styles.chipActive]}
                onPress={() => setUnit(value)}>
                <Text style={[styles.chipText, unit === value && styles.chipTextActive]}>
                  {value}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        <Text style={styles.label}>Đơn giá (₫ / {unit})</Text>
        <TextInput
          style={styles.input}
          value={unitPriceText}
          onChangeText={setUnitPriceText}
          keyboardType="number-pad"
          placeholder="8500"
          placeholderTextColor={colors.textDisabled}
        />

        <Text style={styles.label}>Thành tiền (₫) *</Text>
        <TextInput
          style={[styles.input, styles.amountInput]}
          value={amountText}
          onChangeText={t => {
            setAmountText(t);
            setAmountTouched(true);
          }}
          keyboardType="number-pad"
          placeholder="0"
          placeholderTextColor={colors.textDisabled}
        />
        {amount !== null && amount > 0 && (
          <Text style={styles.amountPreview}>{formatMoney(amount)}</Text>
        )}
        {overridden && (
          <Text style={styles.hint}>
            Khác với {formatMoney(derived)} tính theo sản lượng × đơn giá — số bạn nhập
            được giữ nguyên.
          </Text>
        )}

        <Text style={styles.label}>Ngày bán</Text>
        <DateStepper value={revenueDate} onChange={setRevenueDate} />

        <Text style={styles.label}>Người mua</Text>
        <TextInput
          style={styles.input}
          value={buyer}
          onChangeText={setBuyer}
          placeholder="Thương lái Sáu Tâm"
          placeholderTextColor={colors.textDisabled}
        />

        <Text style={styles.label}>Ghi chú</Text>
        <TextInput
          style={[styles.input, styles.multiline]}
          value={description}
          onChangeText={setDescription}
          multiline
          numberOfLines={3}
          placeholder="Trừ hao độ ẩm, trả trước một phần…"
          placeholderTextColor={colors.textDisabled}
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <TouchableOpacity
          style={[styles.primaryButton, !canSave && styles.buttonDisabled]}
          onPress={onSave}
          disabled={!canSave}>
          <Text style={styles.primaryButtonText}>
            {isEdit ? 'Lưu thay đổi' : 'Ghi khoản thu'}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.secondaryButton} onPress={onCancel}>
          <Text style={styles.secondaryButtonText}>Huỷ</Text>
        </TouchableOpacity>

        {isEdit && (
          <TouchableOpacity style={styles.dangerButton} onPress={onDelete}>
            <Text style={styles.dangerButtonText}>Xoá khoản thu</Text>
          </TouchableOpacity>
        )}
    </FormScaffold>
  );
}

const styles = StyleSheet.create({
  container: {padding: spacing.md, paddingBottom: spacing.xl},
  label: {
    ...typography.label,
    color: colors.text,
    marginTop: spacing.md,
    marginBottom: spacing.xs,
  },
  input: {
    ...typography.body,
    minHeight: MIN_TOUCH_TARGET,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    backgroundColor: colors.surface,
    color: colors.text,
  },
  amountInput: {...typography.title, fontSize: 24, textAlign: 'right'},
  amountPreview: {
    ...typography.label,
    color: colors.success,
    textAlign: 'right',
    marginTop: spacing.xs,
  },
  multiline: {minHeight: 88, textAlignVertical: 'top', paddingTop: spacing.sm},
  hint: {...typography.caption, color: colors.textSecondary, marginTop: spacing.xs, lineHeight: 18},

  row: {flexDirection: 'row', alignItems: 'center'},
  rowInput: {flex: 1, marginRight: spacing.sm},

  chips: {flexDirection: 'row', flexWrap: 'wrap', flex: 1},
  chip: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    marginRight: spacing.xs,
    marginBottom: spacing.xs,
  },
  chipActive: {backgroundColor: colors.primary, borderColor: colors.primary},
  chipText: {...typography.caption, color: colors.textSecondary},
  chipTextActive: {color: colors.textOnPrimary, fontWeight: '600'},

  error: {...typography.caption, color: colors.danger, marginTop: spacing.md},

  primaryButton: {
    minHeight: MIN_TOUCH_TARGET,
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: spacing.lg,
  },
  primaryButtonText: {...typography.heading, color: colors.textOnPrimary},
  buttonDisabled: {backgroundColor: colors.textDisabled},
  secondaryButton: {
    minHeight: MIN_TOUCH_TARGET,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: spacing.sm,
  },
  secondaryButtonText: {...typography.body, color: colors.textSecondary},
  dangerButton: {
    minHeight: MIN_TOUCH_TARGET,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: spacing.lg,
    borderWidth: 1,
    borderColor: colors.danger,
    borderRadius: radius.md,
  },
  dangerButtonText: {...typography.label, color: colors.danger},
});
