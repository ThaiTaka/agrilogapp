/**
 * Thêm / sửa vật tư (Issue #24).
 *
 * Changing `unitCost` here affects FUTURE movements only. Every past
 * transaction keeps the price snapshotted when it happened, so correcting
 * today's price cannot rewrite the cost history of a season that already
 * closed. The form says so, because it is not obvious and a farmer who
 * assumes otherwise would avoid ever updating a price.
 */

import React, {useCallback, useEffect, useState} from 'react';
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

import {database} from '../../db';
import {SUPPLY_CATEGORY_LABELS, SUPPLY_UNITS, SupplyCategory} from '../../db/enums';
import type {Supply} from '../../db/models';
import {ValidationError} from '../../services/seasons';
import {
  archiveSupply,
  createSupply,
  deleteSupply,
  movementCount,
  updateSupply,
} from '../../services/supplies';
import {colors, MIN_TOUCH_TARGET, radius, spacing, typography} from '../../theme';
import {parseNumberInput} from '../../utils/numeric';

const CATEGORIES: SupplyCategory[] = [
  SupplyCategory.FERTILIZER,
  SupplyCategory.PESTICIDE,
  SupplyCategory.SEED,
  SupplyCategory.FUEL,
  SupplyCategory.TOOL,
  SupplyCategory.OTHER,
];

export interface SupplyFormProps {
  supply?: Supply;
  onSaved?: () => void;
  onDeleted?: () => void;
  onCancel?: () => void;
}

export default function SupplyFormScreen({
  supply,
  onSaved,
  onDeleted,
  onCancel,
}: SupplyFormProps) {
  const isEdit = Boolean(supply);

  const [name, setName] = useState(supply?.name ?? '');
  const [category, setCategory] = useState<SupplyCategory>(
    supply?.category ?? SupplyCategory.FERTILIZER,
  );
  const [unit, setUnit] = useState(supply?.unit ?? 'kg');
  const [unitCost, setUnitCost] = useState(
    supply?.unitCost ? String(supply.unitCost) : '',
  );
  const [threshold, setThreshold] = useState(
    supply?.lowStockThreshold ? String(supply.lowStockThreshold).replace('.', ',') : '',
  );
  const [note, setNote] = useState(supply?.note ?? '');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [movements, setMovements] = useState<number | null>(null);

  useEffect(() => {
    if (!supply) {
      return;
    }
    let cancelled = false;
    movementCount(database, supply.id).then(n => {
      if (!cancelled) {
        setMovements(n);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [supply]);

  const canSave = name.trim().length > 0 && unit.trim().length > 0 && !busy;

  const onSave = useCallback(async () => {
    if (!canSave) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const input = {
        name,
        category,
        unit,
        unitCost: parseNumberInput(unitCost) ?? 0,
        lowStockThreshold: parseNumberInput(threshold) ?? 0,
        note: note.trim() || null,
      };
      if (supply) {
        await updateSupply(database, supply.id, input);
      } else {
        await createSupply(database, input);
      }
      onSaved?.();
    } catch (e) {
      setError(
        e instanceof ValidationError ? e.message : 'Không lưu được. Vui lòng thử lại.',
      );
    } finally {
      setBusy(false);
    }
  }, [canSave, name, category, unit, unitCost, threshold, note, supply, onSaved]);

  const onArchive = useCallback(async () => {
    if (!supply) {
      return;
    }
    await archiveSupply(database, supply.id, !supply.isArchived);
    onSaved?.();
  }, [supply, onSaved]);

  const onDelete = useCallback(() => {
    if (!supply) {
      return;
    }
    Alert.alert('Xoá vật tư?', `"${supply.name}" sẽ bị xoá khỏi danh mục.`, [
      {text: 'Huỷ', style: 'cancel'},
      {
        text: 'Xoá',
        style: 'destructive',
        onPress: async () => {
          try {
            await deleteSupply(database, supply.id);
            onDeleted?.();
          } catch (e) {
            setError(e instanceof ValidationError ? e.message : 'Không xoá được.');
          }
        },
      },
    ]);
  }, [supply, onDeleted]);

  const hasHistory = (movements ?? 0) > 0;

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <Text style={styles.label}>Tên vật tư *</Text>
        <TextInput
          style={styles.input}
          value={name}
          onChangeText={setName}
          placeholder="Đạm Urê Phú Mỹ"
          placeholderTextColor={colors.textDisabled}
        />

        <Text style={styles.label}>Nhóm *</Text>
        <View style={styles.chips}>
          {CATEGORIES.map(value => (
            <TouchableOpacity
              key={value}
              style={[styles.chip, category === value && styles.chipActive]}
              onPress={() => setCategory(value)}>
              <Text
                style={[styles.chipText, category === value && styles.chipTextActive]}>
                {SUPPLY_CATEGORY_LABELS[value]}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        <Text style={styles.label}>Đơn vị tính *</Text>
        <View style={styles.chips}>
          {SUPPLY_UNITS.map(value => (
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

        <Text style={styles.label}>Đơn giá (₫ / {unit})</Text>
        <TextInput
          style={styles.input}
          value={unitCost}
          onChangeText={setUnitCost}
          keyboardType="number-pad"
          placeholder="12000"
          placeholderTextColor={colors.textDisabled}
        />
        {isEdit && hasHistory && (
          <Text style={styles.hint}>
            Đổi giá chỉ áp dụng cho lần nhập/xuất sau này. {movements} giao dịch đã ghi
            vẫn giữ nguyên giá tại thời điểm đó.
          </Text>
        )}

        <Text style={styles.label}>Ngưỡng cảnh báo sắp hết</Text>
        <TextInput
          style={styles.input}
          value={threshold}
          onChangeText={setThreshold}
          keyboardType="decimal-pad"
          placeholder="0 = không cảnh báo"
          placeholderTextColor={colors.textDisabled}
        />

        <Text style={styles.label}>Ghi chú</Text>
        <TextInput
          style={[styles.input, styles.multiline]}
          value={note}
          onChangeText={setNote}
          multiline
          numberOfLines={3}
          placeholder="Nhà cung cấp, quy cách…"
          placeholderTextColor={colors.textDisabled}
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <TouchableOpacity
          style={[styles.primaryButton, !canSave && styles.buttonDisabled]}
          onPress={onSave}
          disabled={!canSave}>
          <Text style={styles.primaryButtonText}>
            {isEdit ? 'Lưu thay đổi' : 'Thêm vật tư'}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.secondaryButton} onPress={onCancel}>
          <Text style={styles.secondaryButtonText}>Huỷ</Text>
        </TouchableOpacity>

        {isEdit && (
          <>
            <TouchableOpacity style={styles.outlineButton} onPress={onArchive}>
              <Text style={styles.outlineButtonText}>
                {supply?.isArchived ? 'Bỏ lưu trữ' : 'Lưu trữ (ẩn khỏi danh sách)'}
              </Text>
            </TouchableOpacity>

            {/*
              Deletion is only offered when there is no history. A supply with
              movements must be archived: tombstoning it would drop the row on
              every device and leave last season's diary entries showing a
              blank supply name.
            */}
            {!hasHistory && (
              <TouchableOpacity style={styles.dangerButton} onPress={onDelete}>
                <Text style={styles.dangerButtonText}>Xoá vật tư</Text>
              </TouchableOpacity>
            )}
            {hasHistory && (
              <Text style={styles.hint}>
                Không xoá được vì đã có {movements} giao dịch kho. Hãy lưu trữ để ẩn
                khỏi danh sách mà vẫn giữ lịch sử chi phí.
              </Text>
            )}
          </>
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
  outlineButton: {
    minHeight: MIN_TOUCH_TARGET,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
  },
  outlineButtonText: {...typography.label, color: colors.textSecondary},
  dangerButton: {
    minHeight: MIN_TOUCH_TARGET,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: spacing.sm,
    borderWidth: 1,
    borderColor: colors.danger,
    borderRadius: radius.md,
  },
  dangerButtonText: {...typography.label, color: colors.danger},
});
