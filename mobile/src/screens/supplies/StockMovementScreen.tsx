/**
 * Nhập kho / Xuất kho / Kiểm kê (Issue #24).
 *
 * Three modes on one screen, because they are three answers to the same
 * question — "how much of this do I actually have?" — and splitting them
 * across three screens would just add navigation between things a farmer
 * reaches for interchangeably.
 *
 * Kiểm kê asks for the COUNTED quantity, not a delta. Asking for a delta
 * would make the farmer do arithmetic against a number they do not trust,
 * which is precisely why they are out there counting.
 */

import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {
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
import {TxnType} from '../../db/enums';
import type {Season, StockTransaction, Supply} from '../../db/models';
import {observeSeasons} from '../../services/seasons';
import {
  levelsFrom,
  observeLedger,
  recordStockIn,
  recordStockOut,
  recordStockTake,
} from '../../services/stock';
import {colors, MIN_TOUCH_TARGET, radius, spacing, typography} from '../../theme';
import {formatMoney, formatQuantity, lineTotal, parseNumberInput} from '../../utils/numeric';

// `TxnType` is a const object plus a value-union type, not a TS enum, so its
// members cannot be referenced in type position. The literals are the type.
type Mode = 'in' | 'out' | 'take';

const MODE_LABEL: Record<Mode, string> = {
  in: 'Nhập kho',
  out: 'Xuất kho',
  take: 'Kiểm kê',
};

export interface StockMovementProps {
  supply: Supply;
  onDone?: () => void;
  onCancel?: () => void;
}

export default function StockMovementScreen({
  supply,
  onDone,
  onCancel,
}: StockMovementProps) {
  const [mode, setMode] = useState<Mode>(TxnType.IN);
  const [quantityText, setQuantityText] = useState('');
  const [unitCostText, setUnitCostText] = useState(String(supply.unitCost));
  const [seasonId, setSeasonId] = useState<string | null>(null);
  const [txnDate, setTxnDate] = useState(new Date());
  const [note, setNote] = useState('');
  const [onHand, setOnHand] = useState<number>(0);
  const [seasons, setSeasons] = useState<Season[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<StockTransaction[]>([]);

  // One observed query per supply feeds both the headline balance and the
  // recent-movements list. It replaces a fetch of the ENTIRE ledger that was
  // then filtered in JavaScript — on a phone with two seasons of history that
  // is thousands of rows read to display eight — and being observed rather
  // than fetched also means no setState can land after this screen unmounts.
  useEffect(() => {
    const subs = [
      observeLedger(database, supply.id).subscribe(rows => {
        setOnHand(levelsFrom(rows).get(supply.id) ?? 0);
        setHistory(
          [...rows]
            .sort((a, b) => b.txnDate.getTime() - a.txnDate.getTime())
            .slice(0, 8),
        );
      }),
      observeSeasons(database).subscribe(setSeasons),
    ];
    return () => subs.forEach(s => s.unsubscribe());
  }, [supply.id]);

  const quantity = parseNumberInput(quantityText);
  const unitCost = parseNumberInput(unitCostText) ?? supply.unitCost;

  const preview = useMemo(() => {
    if (quantity === null) {
      return null;
    }
    if (mode === 'take') {
      return {delta: quantity - onHand, result: quantity};
    }
    const delta = mode === TxnType.IN ? quantity : -quantity;
    return {delta, result: onHand + delta};
  }, [quantity, mode, onHand]);

  const canSubmit =
    quantity !== null && !busy && (mode === 'take' ? quantity >= 0 : quantity > 0);

  const onSubmit = useCallback(async () => {
    if (!canSubmit || quantity === null) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      if (mode === 'take') {
        const {transaction} = await recordStockTake(
          database,
          supply.id,
          quantity,
          note.trim() || undefined,
        );
        if (!transaction) {
          // A count matching the ledger writes nothing — saying so is more
          // honest than a success toast for a no-op.
          setError('Số đếm khớp sổ sách — không cần điều chỉnh.');
          setBusy(false);
          return;
        }
      } else {
        const input = {
          supplyId: supply.id,
          quantity,
          unitCost,
          seasonId,
          txnDate,
          note: note.trim() || null,
        };
        if (mode === TxnType.IN) {
          await recordStockIn(database, input);
        } else {
          await recordStockOut(database, input);
        }
      }
      onDone?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không ghi được giao dịch.');
    } finally {
      setBusy(false);
    }
  }, [canSubmit, quantity, mode, supply.id, unitCost, seasonId, txnDate, note, onDone]);

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <View style={styles.header}>
          <Text style={styles.supplyName}>{supply.name}</Text>
          <Text style={styles.onHand}>
            Tồn hiện tại: {formatQuantity(onHand, supply.unit)}
          </Text>
        </View>

        <View style={styles.modeRow}>
          {(['in', 'out', 'take'] as Mode[]).map(value => (
            <TouchableOpacity
              key={value}
              style={[styles.modeChip, mode === value && styles.modeChipActive]}
              onPress={() => {
                setMode(value);
                setError(null);
              }}>
              <Text style={[styles.modeText, mode === value && styles.modeTextActive]}>
                {MODE_LABEL[value]}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        <Text style={styles.label}>
          {mode === 'take' ? `Số đếm thực tế (${supply.unit})` : `Số lượng (${supply.unit})`}
        </Text>
        <TextInput
          style={styles.input}
          value={quantityText}
          onChangeText={t => {
            setQuantityText(t);
            setError(null);
          }}
          keyboardType="decimal-pad"
          placeholder="0"
          placeholderTextColor={colors.textDisabled}
          autoFocus
        />

        {preview && (
          <View style={styles.preview}>
            <Text style={styles.previewLabel}>
              {mode === 'take' ? 'Điều chỉnh' : 'Sau giao dịch'}
            </Text>
            <Text
              style={[
                styles.previewValue,
                preview.result < 0 && styles.previewNegative,
              ]}>
              {mode === 'take'
                ? `${preview.delta > 0 ? '+' : ''}${formatQuantity(preview.delta)} → ${formatQuantity(preview.result, supply.unit)}`
                : formatQuantity(preview.result, supply.unit)}
            </Text>
          </View>
        )}

        {preview && preview.result < 0 && (
          <Text style={styles.warn}>
            Tồn kho sẽ âm — vẫn ghi được, nhớ bổ sung phiếu nhập còn thiếu.
          </Text>
        )}

        {mode !== 'take' && (
          <>
            <Text style={styles.label}>Đơn giá (₫ / {supply.unit})</Text>
            <TextInput
              style={styles.input}
              value={unitCostText}
              onChangeText={setUnitCostText}
              keyboardType="number-pad"
              placeholderTextColor={colors.textDisabled}
            />
            {quantity !== null && (
              <Text style={styles.total}>
                Thành tiền: {formatMoney(lineTotal(quantity, unitCost))}
              </Text>
            )}

            <Text style={styles.label}>Ngày</Text>
            <DateStepper value={txnDate} onChange={setTxnDate} />

            <Text style={styles.label}>Mùa vụ (tuỳ chọn)</Text>
            <View style={styles.chips}>
              <TouchableOpacity
                style={[styles.chip, seasonId === null && styles.chipActive]}
                onPress={() => setSeasonId(null)}>
                <Text
                  style={[styles.chipText, seasonId === null && styles.chipTextActive]}>
                  Không gắn
                </Text>
              </TouchableOpacity>
              {seasons.map(s => (
                <TouchableOpacity
                  key={s.id}
                  style={[styles.chip, seasonId === s.id && styles.chipActive]}
                  onPress={() => setSeasonId(s.id)}>
                  <Text
                    style={[styles.chipText, seasonId === s.id && styles.chipTextActive]}>
                    {s.name}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </>
        )}

        <Text style={styles.label}>Ghi chú</Text>
        <TextInput
          style={styles.input}
          value={note}
          onChangeText={setNote}
          placeholder={mode === 'take' ? 'Lý do chênh lệch…' : 'Mua ở đại lý…'}
          placeholderTextColor={colors.textDisabled}
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <TouchableOpacity
          style={[styles.primaryButton, !canSubmit && styles.buttonDisabled]}
          onPress={onSubmit}
          disabled={!canSubmit}>
          <Text style={styles.primaryButtonText}>{MODE_LABEL[mode]}</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.secondaryButton} onPress={onCancel}>
          <Text style={styles.secondaryButtonText}>Huỷ</Text>
        </TouchableOpacity>

        {history.length > 0 && (
          <View style={styles.history}>
            <Text style={styles.historyTitle}>Gần đây</Text>
            {history.map(txn => (
              <View key={txn.id} style={styles.historyRow}>
                <Text style={styles.historyType}>
                  {txn.txnType === TxnType.IN
                    ? '↓ Nhập'
                    : txn.txnType === TxnType.OUT
                      ? '↑ Xuất'
                      : '⇄ Điều chỉnh'}
                  {txn.diaryEntryId ? ' (từ nhật ký)' : ''}
                </Text>
                <Text style={styles.historyQty}>
                  {formatQuantity(txn.quantity, supply.unit)}
                </Text>
              </View>
            ))}
          </View>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: {flex: 1, backgroundColor: colors.background},
  container: {padding: spacing.md, paddingBottom: spacing.xl},

  header: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
  },
  supplyName: {...typography.heading, color: colors.text},
  onHand: {...typography.body, color: colors.textSecondary, marginTop: spacing.xs},

  modeRow: {flexDirection: 'row', marginTop: spacing.md},
  modeChip: {
    flex: 1,
    minHeight: MIN_TOUCH_TARGET,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    marginRight: spacing.xs,
    borderRadius: radius.md,
  },
  modeChipActive: {backgroundColor: colors.primary, borderColor: colors.primary},
  modeText: {...typography.label, color: colors.textSecondary},
  modeTextActive: {color: colors.textOnPrimary},

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

  preview: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: spacing.sm,
    padding: spacing.sm,
    backgroundColor: '#E8F5E9',
    borderRadius: radius.md,
  },
  previewLabel: {...typography.caption, color: colors.textSecondary},
  previewValue: {...typography.heading, color: colors.primaryDark},
  previewNegative: {color: colors.danger},
  warn: {...typography.caption, color: colors.warning, marginTop: spacing.xs},
  total: {...typography.label, color: colors.primary, marginTop: spacing.xs},

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

  history: {marginTop: spacing.xl},
  historyTitle: {...typography.label, color: colors.textSecondary, marginBottom: spacing.sm},
  historyRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  historyType: {...typography.caption, color: colors.textSecondary},
  historyQty: {...typography.caption, color: colors.text, fontWeight: '600'},
});
