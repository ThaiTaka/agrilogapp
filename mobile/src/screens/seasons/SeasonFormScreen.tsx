/**
 * Tạo / sửa mùa vụ (Issue #20).
 *
 * Saves straight to WatermelonDB and pops. No spinner, no network, no failure
 * path to design — pressing "Lưu" cannot fail for connectivity reasons,
 * which is the whole promise of the app.
 */

import React, {useCallback, useState} from 'react';
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
import {AREA_UNITS, SEASON_STATUS_LABELS, SeasonStatus} from '../../db/enums';
import type {Season} from '../../db/models';
import {
  createSeason,
  deleteSeason,
  updateSeason,
  ValidationError,
} from '../../services/seasons';
import {colors, MIN_TOUCH_TARGET, radius, spacing, typography} from '../../theme';
import {startOfLocalDay} from '../../utils/date';
import {parseNumberInput} from '../../utils/numeric';

const STATUSES: SeasonStatus[] = [
  SeasonStatus.PLANNING,
  SeasonStatus.ACTIVE,
  SeasonStatus.HARVESTED,
  SeasonStatus.CLOSED,
];

export interface SeasonFormProps {
  season?: Season;
  onSaved?: (season: Season) => void;
  onDeleted?: () => void;
  onCancel?: () => void;
}

export default function SeasonFormScreen({
  season,
  onSaved,
  onDeleted,
  onCancel,
}: SeasonFormProps) {
  const isEdit = Boolean(season);

  const [name, setName] = useState(season?.name ?? '');
  const [cropType, setCropType] = useState(season?.cropType ?? '');
  const [areaSize, setAreaSize] = useState(
    season?.areaSize != null ? String(season.areaSize).replace('.', ',') : '',
  );
  const [areaUnit, setAreaUnit] = useState(season?.areaUnit ?? 'sao');
  const [status, setStatus] = useState<SeasonStatus>(season?.status ?? SeasonStatus.ACTIVE);
  const [note, setNote] = useState(season?.note ?? '');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Snapped on the way in so an untouched start date compares cleanly against
  // an end date the farmer picks — DateStepper only snaps what it is used on.
  const [startDate, setStartDate] = useState<Date>(
    startOfLocalDay(season?.startDate ?? new Date()),
  );
  const [endDate, setEndDate] = useState<Date | null>(season?.endDate ?? null);

  // `maxToday` is off for both: unlike a diary entry, which records what
  // happened, a season is routinely created before it starts and given a
  // planned harvest date.
  const endBeforeStart =
    endDate !== null && endDate.getTime() < startDate.getTime();

  const canSave =
    name.trim().length > 0 && cropType.trim().length > 0 && !endBeforeStart && !busy;

  const onSave = useCallback(async () => {
    if (!canSave) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const input = {
        name,
        cropType,
        areaSize: parseNumberInput(areaSize),
        areaUnit,
        startDate,
        endDate,
        status,
        note: note.trim() || null,
      };
      const saved = season
        ? await updateSeason(database, season.id, input)
        : await createSeason(database, input);
      onSaved?.(saved);
    } catch (e) {
      setError(
        e instanceof ValidationError ? e.message : 'Không lưu được. Vui lòng thử lại.',
      );
    } finally {
      setBusy(false);
    }
  }, [
    canSave,
    name,
    cropType,
    areaSize,
    areaUnit,
    startDate,
    endDate,
    status,
    note,
    season,
    onSaved,
  ]);

  const onDelete = useCallback(() => {
    if (!season) {
      return;
    }
    // Confirmed because the cascade is far larger than the tap suggests, and
    // the dialog says exactly what goes with it.
    Alert.alert(
      'Xoá mùa vụ?',
      `Toàn bộ nhật ký, chi phí và doanh thu của "${season.name}" sẽ bị xoá. ` +
        'Vật tư đã dùng trong nhật ký sẽ được hoàn lại kho.',
      [
        {text: 'Huỷ', style: 'cancel'},
        {
          text: 'Xoá',
          style: 'destructive',
          onPress: async () => {
            const result = await deleteSeason(database, season.id);
            Alert.alert(
              'Đã xoá',
              `${result.diaryEntries} nhật ký, ${result.expenses} khoản chi, ` +
                `${result.revenues} khoản thu.\n` +
                `${result.transactionsReversed} lượt dùng vật tư đã hoàn kho, ` +
                `${result.transactionsUnlinked} giao dịch mua được giữ lại.`,
            );
            onDeleted?.();
          },
        },
      ],
    );
  }, [season, onDeleted]);

  return (
    <FormScaffold contentContainerStyle={styles.container}>
        <Text style={styles.label}>Tên mùa vụ *</Text>
        <TextInput
          style={styles.input}
          value={name}
          onChangeText={setName}
          placeholder="Vụ Đông Xuân 2026"
          placeholderTextColor={colors.textDisabled}
        />

        <Text style={styles.label}>Loại cây trồng *</Text>
        <TextInput
          style={styles.input}
          value={cropType}
          onChangeText={setCropType}
          placeholder="Lúa, Cà chua, Bắp cải…"
          placeholderTextColor={colors.textDisabled}
        />

        <Text style={styles.label}>Diện tích</Text>
        <View style={styles.row}>
          <TextInput
            style={[styles.input, styles.rowInput]}
            value={areaSize}
            onChangeText={setAreaSize}
            keyboardType="decimal-pad"
            placeholder="5"
            placeholderTextColor={colors.textDisabled}
          />
          <View style={styles.chips}>
            {AREA_UNITS.map(unit => (
              <TouchableOpacity
                key={unit}
                style={[styles.chip, areaUnit === unit && styles.chipActive]}
                onPress={() => setAreaUnit(unit)}>
                <Text
                  style={[styles.chipText, areaUnit === unit && styles.chipTextActive]}>
                  {unit}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        <Text style={styles.label}>Trạng thái</Text>
        <View style={styles.chips}>
          {STATUSES.map(value => (
            <TouchableOpacity
              key={value}
              style={[styles.chip, status === value && styles.chipActive]}
              onPress={() => setStatus(value)}>
              <Text style={[styles.chipText, status === value && styles.chipTextActive]}>
                {SEASON_STATUS_LABELS[value]}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        <Text style={styles.label}>Ngày bắt đầu</Text>
        <DateStepper value={startDate} onChange={setStartDate} maxToday={false} />

        <Text style={styles.label}>Ngày kết thúc</Text>
        <View style={styles.chips}>
          <TouchableOpacity
            style={[styles.chip, endDate === null && styles.chipActive]}
            onPress={() => setEndDate(null)}>
            <Text
              style={[styles.chipText, endDate === null && styles.chipTextActive]}>
              Chưa kết thúc
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.chip, endDate !== null && styles.chipActive]}
            // Seeded from the start date, not from today: a season created in
            // advance would otherwise open its end picker on a date before it
            // begins.
            onPress={() => setEndDate(current => current ?? startDate)}>
            <Text
              style={[styles.chipText, endDate !== null && styles.chipTextActive]}>
              Chọn ngày
            </Text>
          </TouchableOpacity>
        </View>

        {endDate !== null && (
          <View style={styles.endPicker}>
            <DateStepper value={endDate} onChange={setEndDate} maxToday={false} />
          </View>
        )}

        {endBeforeStart && (
          <Text style={styles.hintInline}>
            Ngày kết thúc đang trước ngày bắt đầu — sửa lại để lưu được.
          </Text>
        )}

        <Text style={styles.label}>Ghi chú</Text>
        <TextInput
          style={[styles.input, styles.multiline]}
          value={note}
          onChangeText={setNote}
          multiline
          numberOfLines={3}
          placeholder="Giống, nguồn nước, lưu ý riêng…"
          placeholderTextColor={colors.textDisabled}
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <TouchableOpacity
          style={[styles.primaryButton, !canSave && styles.buttonDisabled]}
          onPress={onSave}
          disabled={!canSave}>
          <Text style={styles.primaryButtonText}>
            {isEdit ? 'Lưu thay đổi' : 'Tạo mùa vụ'}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.secondaryButton} onPress={onCancel}>
          <Text style={styles.secondaryButtonText}>Huỷ</Text>
        </TouchableOpacity>

        {isEdit && (
          <TouchableOpacity style={styles.dangerButton} onPress={onDelete}>
            <Text style={styles.dangerButtonText}>Xoá mùa vụ</Text>
          </TouchableOpacity>
        )}
    </FormScaffold>
  );
}

const styles = StyleSheet.create({
  container: {padding: spacing.md, paddingBottom: spacing.xl},
  label: {...typography.label, color: colors.text, marginTop: spacing.md, marginBottom: spacing.xs},
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
  row: {flexDirection: 'row', alignItems: 'center'},
  rowInput: {flex: 1, marginRight: spacing.sm},
  endPicker: {marginTop: spacing.xs},
  // Secondary, not danger: it says what to do next, it does not scold.
  hintInline: {...typography.caption, color: colors.textSecondary, marginTop: spacing.xs},

  chips: {flexDirection: 'row', flexWrap: 'wrap', flex: 1},
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
