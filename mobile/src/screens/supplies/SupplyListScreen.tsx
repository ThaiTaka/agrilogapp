/**
 * Kho vật tư (Issue #24).
 *
 * On-hand is computed from the ledger on every render pass, never read from a
 * stored counter (D1). Levels are loaded for the whole page in one grouped
 * pass, so a 40-item inventory is one query rather than 41.
 */

import {withObservables} from '@nozbe/watermelondb/react';
import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {FlatList, StyleSheet, Text, TextInput, TouchableOpacity, View} from 'react-native';

import SyncStatusBar from '../../components/SyncStatusBar';
import {database} from '../../db';
import {SUPPLY_CATEGORY_LABELS, SupplyCategory} from '../../db/enums';
import type {Supply} from '../../db/models';
import {isLowStock, stockLevels} from '../../services/stock';
import {observeSupplies} from '../../services/supplies';
import {colors, MIN_TOUCH_TARGET, radius, spacing, typography} from '../../theme';
import {formatMoney, formatQuantity} from '../../utils/numeric';

const CATEGORY_ICON: Record<SupplyCategory, string> = {
  fertilizer: '💊',
  pesticide: '🧴',
  seed: '🌰',
  fuel: '⛽',
  tool: '🔧',
  other: '📦',
};

function SupplyCard({
  supply,
  onHand,
  onPress,
  onMove,
}: {
  supply: Supply;
  onHand: number;
  onPress: (s: Supply) => void;
  onMove: (s: Supply) => void;
}) {
  const low = isLowStock(supply, onHand);
  const negative = onHand < 0;

  return (
    <View style={styles.card}>
      <TouchableOpacity style={styles.cardMain} onPress={() => onPress(supply)}>
        <Text style={styles.cardIcon}>{CATEGORY_ICON[supply.category]}</Text>
        <View style={styles.cardText}>
          <Text style={styles.cardName} numberOfLines={1}>
            {supply.name}
          </Text>
          <Text style={styles.cardMeta}>
            {SUPPLY_CATEGORY_LABELS[supply.category]} · {formatMoney(supply.unitCost)}/
            {supply.unit}
          </Text>
        </View>

        <View style={styles.cardStock}>
          <Text
            style={[
              styles.stockValue,
              negative && styles.stockNegative,
              !negative && low && styles.stockLow,
            ]}>
            {formatQuantity(onHand)}
          </Text>
          <Text style={styles.stockUnit}>{supply.unit}</Text>
        </View>
      </TouchableOpacity>

      {(low || negative) && (
        <Text style={[styles.flag, negative ? styles.flagNegative : styles.flagLow]}>
          {negative
            ? 'Tồn âm — có lần dùng chưa ghi phiếu nhập'
            : `Sắp hết (ngưỡng ${formatQuantity(supply.lowStockThreshold, supply.unit)})`}
        </Text>
      )}

      <TouchableOpacity style={styles.moveButton} onPress={() => onMove(supply)}>
        <Text style={styles.moveButtonText}>Nhập / Xuất / Kiểm kê</Text>
      </TouchableOpacity>
    </View>
  );
}

interface Props {
  supplies: Supply[];
  onSelectSupply?: (supply: Supply) => void;
  onMoveStock?: (supply: Supply) => void;
  onCreateSupply?: () => void;
}

export function SupplyListScreen({
  supplies,
  onSelectSupply,
  onMoveStock,
  onCreateSupply,
}: Props) {
  const [levels, setLevels] = useState<Map<string, number>>(new Map());
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState<SupplyCategory | null>(null);
  const [lowOnly, setLowOnly] = useState(false);

  useEffect(() => {
    let cancelled = false;
    stockLevels(database).then(next => {
      if (!cancelled) {
        setLevels(next);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [supplies]);

  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return supplies.filter(s => {
      if (needle && !s.name.toLowerCase().includes(needle)) {
        return false;
      }
      if (category && s.category !== category) {
        return false;
      }
      if (lowOnly && !isLowStock(s, levels.get(s.id) ?? 0)) {
        return false;
      }
      return true;
    });
  }, [supplies, search, category, lowOnly, levels]);

  const lowCount = useMemo(
    () => supplies.filter(s => isLowStock(s, levels.get(s.id) ?? 0)).length,
    [supplies, levels],
  );

  const presentCategories = useMemo(
    () => [...new Set(supplies.map(s => s.category))],
    [supplies],
  );

  const handleSelect = useCallback(
    (s: Supply) => onSelectSupply?.(s),
    [onSelectSupply],
  );
  const handleMove = useCallback((s: Supply) => onMoveStock?.(s), [onMoveStock]);

  return (
    <View style={styles.container}>
      <SyncStatusBar />

      {supplies.length > 0 && (
        <View style={styles.filters}>
          <TextInput
            style={styles.search}
            value={search}
            onChangeText={setSearch}
            placeholder="Tìm vật tư…"
            placeholderTextColor={colors.textDisabled}
          />

          <View style={styles.chipRow}>
            {lowCount > 0 && (
              <TouchableOpacity
                style={[styles.chip, lowOnly && styles.chipWarnActive]}
                onPress={() => setLowOnly(!lowOnly)}>
                <Text style={[styles.chipText, lowOnly && styles.chipTextActive]}>
                  ⚠ Sắp hết ({lowCount})
                </Text>
              </TouchableOpacity>
            )}
            {presentCategories.map(c => (
              <TouchableOpacity
                key={c}
                style={[styles.chip, category === c && styles.chipActive]}
                onPress={() => setCategory(category === c ? null : c)}>
                <Text style={[styles.chipText, category === c && styles.chipTextActive]}>
                  {CATEGORY_ICON[c]} {SUPPLY_CATEGORY_LABELS[c]}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      )}

      <FlatList
        data={visible}
        keyExtractor={s => s.id}
        renderItem={({item}) => (
          <SupplyCard
            supply={item}
            onHand={levels.get(item.id) ?? 0}
            onPress={handleSelect}
            onMove={handleMove}
          />
        )}
        contentContainerStyle={
          visible.length === 0 ? styles.listEmpty : styles.listContent
        }
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyIcon}>📦</Text>
            <Text style={styles.emptyTitle}>
              {supplies.length === 0 ? 'Chưa có vật tư nào' : 'Không tìm thấy'}
            </Text>
            <Text style={styles.emptyText}>
              {supplies.length === 0
                ? 'Thêm phân bón, thuốc, giống… để ghi được lượng dùng trong nhật ký và tính chi phí tự động.'
                : 'Thử bỏ bớt bộ lọc.'}
            </Text>
            {supplies.length === 0 && (
              <TouchableOpacity style={styles.emptyButton} onPress={onCreateSupply}>
                <Text style={styles.emptyButtonText}>Thêm vật tư</Text>
              </TouchableOpacity>
            )}
          </View>
        }
        initialNumToRender={8}
        maxToRenderPerBatch={8}
        windowSize={7}
        removeClippedSubviews
      />

      {supplies.length > 0 && (
        <TouchableOpacity
          style={styles.fab}
          onPress={onCreateSupply}
          accessibilityRole="button"
          accessibilityLabel="Thêm vật tư">
          <Text style={styles.fabText}>+</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const enhance = withObservables([], () => ({
  supplies: observeSupplies(database),
}));

export default enhance(SupplyListScreen);

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: colors.background},

  filters: {
    paddingHorizontal: spacing.md,
    paddingTop: spacing.sm,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  search: {
    ...typography.body,
    minHeight: MIN_TOUCH_TARGET,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    color: colors.text,
  },
  chipRow: {flexDirection: 'row', flexWrap: 'wrap', marginTop: spacing.sm},
  chip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    marginRight: spacing.xs,
    marginBottom: spacing.sm,
  },
  chipActive: {backgroundColor: colors.primary, borderColor: colors.primary},
  chipWarnActive: {backgroundColor: colors.warning, borderColor: colors.warning},
  chipText: {...typography.caption, color: colors.textSecondary},
  chipTextActive: {color: colors.textOnPrimary, fontWeight: '600'},

  listContent: {padding: spacing.md, paddingBottom: 96},
  listEmpty: {flexGrow: 1},

  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.sm,
    overflow: 'hidden',
  },
  cardMain: {flexDirection: 'row', alignItems: 'center', padding: spacing.md},
  cardIcon: {fontSize: 28, marginRight: spacing.sm},
  cardText: {flex: 1},
  cardName: {...typography.heading, color: colors.text},
  cardMeta: {...typography.caption, color: colors.textSecondary, marginTop: 2},
  cardStock: {alignItems: 'flex-end', minWidth: 72},
  stockValue: {...typography.title, fontSize: 20, color: colors.text},
  stockLow: {color: colors.warning},
  stockNegative: {color: colors.danger},
  stockUnit: {...typography.caption, color: colors.textSecondary},

  flag: {
    ...typography.caption,
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.sm,
  },
  flagLow: {color: colors.warning},
  flagNegative: {color: colors.danger},

  moveButton: {
    minHeight: MIN_TOUCH_TARGET,
    alignItems: 'center',
    justifyContent: 'center',
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: '#FAFAFA',
  },
  moveButtonText: {...typography.label, color: colors.primary},

  empty: {flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.lg},
  emptyIcon: {fontSize: 56},
  emptyTitle: {...typography.title, color: colors.text, marginTop: spacing.md},
  emptyText: {
    ...typography.body,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: spacing.sm,
    lineHeight: 22,
  },
  emptyButton: {
    minHeight: MIN_TOUCH_TARGET,
    paddingHorizontal: spacing.lg,
    justifyContent: 'center',
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    marginTop: spacing.lg,
  },
  emptyButtonText: {...typography.heading, color: colors.textOnPrimary},

  fab: {
    position: 'absolute',
    right: spacing.lg,
    bottom: spacing.lg,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    elevation: 4,
  },
  fabText: {fontSize: 32, color: colors.textOnPrimary, lineHeight: 36},
});
