/**
 * Ghi / sửa khoản chi thủ công (Issue #28).
 *
 * A `diary_auto` expense opens READ-ONLY. The farmer still gets to see it —
 * hiding it would make the season total look wrong — but the form explains
 * where the number came from and sends them to the diary entry instead of
 * letting them edit a derived value (D7).
 */

import React, {useCallback, useState} from 'react';
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';

import DateStepper from '../../components/DateStepper';
import {database} from '../../db';
import {EXPENSE_CATEGORY_LABELS, ExpenseCategory} from '../../db/enums';
import type {Expense} from '../../db/models';
import {createExpense, deleteExpense, updateExpense} from '../../services/finance';
import {ValidationError} from '../../services/seasons';
import {colors, MIN_TOUCH_TARGET, radius, spacing, typography} from '../../theme';
import {formatDate} from '../../utils/date';
import {formatMoney, parseNumberInput} from '../../utils/numeric';

const CATEGORIES: ExpenseCategory[] = [
  ExpenseCategory.LABOR,
  ExpenseCategory.MACHINERY,
  ExpenseCategory.TRANSPORT,
  ExpenseCategory.LAND_RENT,
  ExpenseCategory.IRRIGATION,
  ExpenseCategory.SUPPLY,
  ExpenseCategory.OTHER,
];

export interface ExpenseFormProps {
  seasonId: string;
  expense?: Expense;
  onSaved?: () => void;
  onDeleted?: () => void;
  onCancel?: () => void;
}

function ReadOnlyNotice({expense, onClose}: {expense: Expense; onClose?: () => void}) {
  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.autoCard}>
        <Text style={styles.autoIcon}>🔗</Text>
        <Text style={styles.autoTitle}>Khoản chi tự động</Text>
        <Text style={styles.autoAmount}>{formatMoney(expense.amount)}</Text>
        <Text style={styles.autoDate}>{formatDate(expense.expenseDate)}</Text>

        <Text style={styles.autoBody}>
          Khoản chi này được tạo tự động từ lượng vật tư bạn đã ghi trong nhật ký
          canh tác, nên không sửa trực tiếp ở đây.
        </Text>
        <Text style={styles.autoBody}>
          Muốn thay đổi số tiền, hãy sửa lượng vật tư trong nhật ký tương ứng —
          khoản chi sẽ tự cập nhật theo.
        </Text>
      </View>

      <TouchableOpacity style={styles.secondaryButton} onPress={onClose}>
        <Text style={styles.secondaryButtonText}>Đóng</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

export default function ExpenseFormScreen({
  seasonId,
  expense,
  onSaved,
  onDeleted,
  onCancel,
}: ExpenseFormProps) {
  const isEdit = Boolean(expense);

  const [category, setCategory] = useState<ExpenseCategory>(
    expense?.category ?? ExpenseCategory.LABOR,
  );
  // `!= null`, not a truthiness test: a 0 ₫ expense is a real record (a gift, a
  // waived fee) and opened with the amount field blank, which then failed to
  // save because a blank amount is not a number.
  const [amountText, setAmountText] = useState(
    expense?.amount != null ? String(expense.amount) : '',
  );
  const [expenseDate, setExpenseDate] = useState(expense?.expenseDate ?? new Date());
  const [description, setDescription] = useState(expense?.description ?? '');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const amount = parseNumberInput(amountText);
  const canSave = amount !== null && amount >= 0 && !busy;

  const onSave = useCallback(async () => {
    if (!canSave || amount === null) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const input = {
        seasonId,
        category,
        amount,
        expenseDate,
        description: description.trim() || null,
      };
      if (expense) {
        await updateExpense(database, expense.id, input);
      } else {
        await createExpense(database, input);
      }
      onSaved?.();
    } catch (e) {
      setError(
        e instanceof ValidationError ? e.message : 'Không lưu được. Vui lòng thử lại.',
      );
    } finally {
      setBusy(false);
    }
  }, [canSave, amount, seasonId, category, expenseDate, description, expense, onSaved]);

  const onDelete = useCallback(() => {
    if (!expense) {
      return;
    }
    Alert.alert('Xoá khoản chi?', formatMoney(expense.amount), [
      {text: 'Huỷ', style: 'cancel'},
      {
        text: 'Xoá',
        style: 'destructive',
        onPress: async () => {
          try {
            await deleteExpense(database, expense.id);
            onDeleted?.();
          } catch (e) {
            setError(e instanceof ValidationError ? e.message : 'Không xoá được.');
          }
        },
      },
    ]);
  }, [expense, onDeleted]);

  if (expense && !expense.isEditable) {
    return <ReadOnlyNotice expense={expense} onClose={onCancel} />;
  }

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <Text style={styles.label}>Số tiền (₫) *</Text>
        <TextInput
          style={[styles.input, styles.amountInput]}
          value={amountText}
          onChangeText={setAmountText}
          keyboardType="number-pad"
          placeholder="0"
          placeholderTextColor={colors.textDisabled}
          autoFocus={!isEdit}
        />
        {amount !== null && amount > 0 && (
          <Text style={styles.amountPreview}>{formatMoney(amount)}</Text>
        )}

        <Text style={styles.label}>Loại chi phí *</Text>
        <View style={styles.chips}>
          {CATEGORIES.map(value => (
            <TouchableOpacity
              key={value}
              style={[styles.chip, category === value && styles.chipActive]}
              onPress={() => setCategory(value)}>
              <Text
                style={[styles.chipText, category === value && styles.chipTextActive]}>
                {EXPENSE_CATEGORY_LABELS[value]}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
        {category === ExpenseCategory.SUPPLY && (
          <Text style={styles.hint}>
            Chi phí vật tư thường tự sinh từ nhật ký. Chỉ nhập tay ở đây nếu đây là
            khoản mua không ghi qua kho.
          </Text>
        )}

        <Text style={styles.label}>Ngày chi</Text>
        <DateStepper value={expenseDate} onChange={setExpenseDate} />

        <Text style={styles.label}>Diễn giải</Text>
        <TextInput
          style={[styles.input, styles.multiline]}
          value={description}
          onChangeText={setDescription}
          multiline
          numberOfLines={3}
          placeholder="Thuê 3 công cấy…"
          placeholderTextColor={colors.textDisabled}
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <TouchableOpacity
          style={[styles.primaryButton, !canSave && styles.buttonDisabled]}
          onPress={onSave}
          disabled={!canSave}>
          <Text style={styles.primaryButtonText}>
            {isEdit ? 'Lưu thay đổi' : 'Ghi khoản chi'}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.secondaryButton} onPress={onCancel}>
          <Text style={styles.secondaryButtonText}>Huỷ</Text>
        </TouchableOpacity>

        {isEdit && (
          <TouchableOpacity style={styles.dangerButton} onPress={onDelete}>
            <Text style={styles.dangerButtonText}>Xoá khoản chi</Text>
          </TouchableOpacity>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: {flex: 1, backgroundColor: colors.background},
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
    color: colors.primary,
    textAlign: 'right',
    marginTop: spacing.xs,
  },
  multiline: {minHeight: 88, textAlignVertical: 'top', paddingTop: spacing.sm},
  hint: {...typography.caption, color: colors.textSecondary, marginTop: spacing.xs, lineHeight: 18},

  chips: {flexDirection: 'row', flexWrap: 'wrap'},
  chip: {
    paddingHorizontal: spacing.md,
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

  autoCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.info,
    padding: spacing.lg,
    alignItems: 'center',
  },
  autoIcon: {fontSize: 40},
  autoTitle: {...typography.heading, color: colors.info, marginTop: spacing.sm},
  autoAmount: {...typography.title, fontSize: 28, color: colors.text, marginTop: spacing.sm},
  autoDate: {...typography.caption, color: colors.textSecondary},
  autoBody: {
    ...typography.body,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: spacing.md,
    lineHeight: 22,
  },
});
