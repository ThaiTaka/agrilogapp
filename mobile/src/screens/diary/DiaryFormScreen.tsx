/**
 * Ghi / sửa nhật ký canh tác (Issue #22).
 *
 * Writes straight to WatermelonDB through diary.ts, which handles the stock
 * movements and the auto-generated expense in the same writer block. There is
 * no network path and therefore no failure state to design for — pressing
 * "Lưu" in the middle of a field with no signal behaves exactly like pressing
 * it at home.
 */

import React, {useCallback, useEffect, useMemo, useState} from 'react';
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
import SupplyUsageEditor, {type UsageRow} from '../../components/SupplyUsageEditor';
import {database} from '../../db';
import {
  WEATHER_LABELS,
  WEATHER_VALUES,
  WORK_TYPE_LABELS,
  WorkType,
} from '../../db/enums';
import type {DiaryEntry, StockTransaction, Supply} from '../../db/models';
import {
  createDiaryEntry,
  deleteDiaryEntry,
  updateDiaryEntry,
} from '../../services/diary';
import {stockLevels} from '../../services/stock';
import {colors, MIN_TOUCH_TARGET, radius, spacing, typography} from '../../theme';
import {parseNumberInput} from '../../utils/numeric';

const WORK_TYPES: WorkType[] = [
  WorkType.LAND_PREP,
  WorkType.SOWING,
  WorkType.FERTILIZING,
  WorkType.SPRAYING,
  WorkType.WATERING,
  WorkType.WEEDING,
  WorkType.HARVESTING,
  WorkType.OTHER,
];

export interface DiaryFormProps {
  seasonId: string;
  entry?: DiaryEntry;
  existingUsages?: StockTransaction[];
  onSaved?: () => void;
  onDeleted?: () => void;
  onCancel?: () => void;
}

export default function DiaryFormScreen({
  seasonId,
  entry,
  existingUsages = [],
  onSaved,
  onDeleted,
  onCancel,
}: DiaryFormProps) {
  const isEdit = Boolean(entry);

  const [workType, setWorkType] = useState<WorkType>(entry?.workType ?? WorkType.FERTILIZING);
  const [entryDate, setEntryDate] = useState<Date>(entry?.entryDate ?? new Date());
  const [title, setTitle] = useState(entry?.title ?? '');
  const [note, setNote] = useState(entry?.note ?? '');
  const [weather, setWeather] = useState<string | null>(entry?.weather ?? null);
  const [laborHours, setLaborHours] = useState(
    entry?.laborHours != null ? String(entry.laborHours).replace('.', ',') : '',
  );

  const [supplies, setSupplies] = useState<Supply[]>([]);
  const [levels, setLevels] = useState<Map<string, number>>(new Map());
  const [rows, setRows] = useState<UsageRow[]>(() =>
    existingUsages.map(t => ({
      supplyId: t.supplyId,
      quantityText: String(t.quantity).replace('.', ','),
    })),
  );

  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const all = await database.get<Supply>('supplies').query().fetch();
      const current = await stockLevels(database);
      if (!cancelled) {
        setSupplies(all);
        setLevels(current);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const usageInputs = useMemo(
    () =>
      rows
        .map(r => ({supplyId: r.supplyId, quantity: parseNumberInput(r.quantityText)}))
        .filter((u): u is {supplyId: string; quantity: number} => u.quantity !== null),
    [rows],
  );

  const hasIncompleteRow = rows.some(r => parseNumberInput(r.quantityText) === null);
  const hasNonPositive = usageInputs.some(u => u.quantity <= 0);
  const canSave = !busy && !hasIncompleteRow && !hasNonPositive;

  const onSave = useCallback(async () => {
    if (!canSave) {
      setError(
        hasNonPositive
          ? 'Số lượng vật tư phải lớn hơn 0.'
          : 'Hãy nhập số lượng cho mọi vật tư đã chọn, hoặc bỏ dòng đó đi.',
      );
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const payload = {
        seasonId,
        workType,
        entryDate,
        title: title.trim() || null,
        note: note.trim() || null,
        weather,
        laborHours: parseNumberInput(laborHours),
        supplyUsages: usageInputs,
      };

      if (entry) {
        await updateDiaryEntry(database, entry.id, payload);
      } else {
        await createDiaryEntry(database, payload);
      }
      onSaved?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không lưu được. Vui lòng thử lại.');
    } finally {
      setBusy(false);
    }
  }, [
    canSave,
    hasNonPositive,
    seasonId,
    workType,
    entryDate,
    title,
    note,
    weather,
    laborHours,
    usageInputs,
    entry,
    onSaved,
  ]);

  const onDelete = useCallback(() => {
    if (!entry) {
      return;
    }
    const restoring = existingUsages.length;
    Alert.alert(
      'Xoá nhật ký?',
      restoring > 0
        ? `${restoring} khoản vật tư sẽ được hoàn lại kho và khoản chi tương ứng sẽ bị xoá.`
        : 'Nhật ký này sẽ bị xoá.',
      [
        {text: 'Huỷ', style: 'cancel'},
        {
          text: 'Xoá',
          style: 'destructive',
          onPress: async () => {
            const result = await deleteDiaryEntry(database, entry.id);
            if (result.transactionsReversed > 0) {
              Alert.alert(
                'Đã hoàn kho',
                `${result.transactionsReversed} khoản vật tư đã trả về kho.`,
              );
            }
            onDeleted?.();
          },
        },
      ],
    );
  }, [entry, existingUsages.length, onDeleted]);

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <Text style={styles.label}>Loại công việc *</Text>
        <View style={styles.chips}>
          {WORK_TYPES.map(value => (
            <TouchableOpacity
              key={value}
              style={[styles.chip, workType === value && styles.chipActive]}
              onPress={() => setWorkType(value)}>
              <Text
                style={[styles.chipText, workType === value && styles.chipTextActive]}>
                {WORK_TYPE_LABELS[value]}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        <Text style={styles.label}>Ngày thực hiện</Text>
        <DateStepper value={entryDate} onChange={setEntryDate} />

        <Text style={styles.label}>Vật tư đã dùng</Text>
        <SupplyUsageEditor
          supplies={supplies}
          rows={rows}
          onChange={setRows}
          stockLevels={levels}
        />

        <Text style={styles.label}>Thời tiết</Text>
        <View style={styles.chips}>
          {WEATHER_VALUES.map(value => (
            <TouchableOpacity
              key={value}
              style={[styles.chip, weather === value && styles.chipActive]}
              onPress={() => setWeather(weather === value ? null : value)}>
              <Text style={[styles.chipText, weather === value && styles.chipTextActive]}>
                {WEATHER_LABELS[value]}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        <Text style={styles.label}>Số giờ công</Text>
        <TextInput
          style={styles.input}
          value={laborHours}
          onChangeText={setLaborHours}
          keyboardType="decimal-pad"
          placeholder="Ví dụ: 4"
          placeholderTextColor={colors.textDisabled}
        />

        <Text style={styles.label}>Tiêu đề</Text>
        <TextInput
          style={styles.input}
          value={title}
          onChangeText={setTitle}
          placeholder="Bón thúc đợt 1"
          placeholderTextColor={colors.textDisabled}
          maxLength={160}
        />

        <Text style={styles.label}>Ghi chú</Text>
        <TextInput
          style={[styles.input, styles.multiline]}
          value={note}
          onChangeText={setNote}
          multiline
          numberOfLines={3}
          placeholder="Chi tiết công việc, tình trạng cây trồng…"
          placeholderTextColor={colors.textDisabled}
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <TouchableOpacity
          style={[styles.primaryButton, !canSave && styles.buttonDisabled]}
          onPress={onSave}
          disabled={busy}>
          <Text style={styles.primaryButtonText}>
            {isEdit ? 'Lưu thay đổi' : 'Ghi nhật ký'}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.secondaryButton} onPress={onCancel}>
          <Text style={styles.secondaryButtonText}>Huỷ</Text>
        </TouchableOpacity>

        {isEdit && (
          <TouchableOpacity style={styles.dangerButton} onPress={onDelete}>
            <Text style={styles.dangerButtonText}>Xoá nhật ký</Text>
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
  multiline: {minHeight: 88, textAlignVertical: 'top', paddingTop: spacing.sm},

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
});
