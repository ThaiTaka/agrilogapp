/**
 * Nhật ký của một mùa vụ (Issue #22).
 *
 * Observable query, so an entry written on another device appears here the
 * moment sync lands it — no refresh, because there is nothing to refresh
 * from.
 */

import {Q} from '@nozbe/watermelondb';
import {withObservables} from '@nozbe/watermelondb/react';
import React, {useCallback, useEffect, useState} from 'react';
import {FlatList, StyleSheet, Text, TouchableOpacity, View} from 'react-native';

import {database} from '../../db';
import {WEATHER_LABELS, WORK_TYPE_LABELS, WorkType} from '../../db/enums';
import type {DiaryEntry, Season, StockTransaction} from '../../db/models';
import {colors, radius, spacing, typography} from '../../theme';
import {formatDate} from '../../utils/date';
import {formatMoney, formatQuantity} from '../../utils/numeric';

const WORK_TYPE_ICON: Record<WorkType, string> = {
  land_prep: '🚜',
  sowing: '🌱',
  fertilizing: '💊',
  spraying: '🧴',
  watering: '💧',
  weeding: '🌿',
  harvesting: '🌾',
  other: '📝',
};

interface UsageSummary {
  cost: number;
  lines: {name: string; quantity: number; unit: string}[];
}

function EntryCard({
  entry,
  usage,
  onPress,
}: {
  entry: DiaryEntry;
  usage?: UsageSummary;
  onPress: (e: DiaryEntry) => void;
}) {
  return (
    <TouchableOpacity style={styles.card} onPress={() => onPress(entry)}>
      <View style={styles.cardHeader}>
        <Text style={styles.cardIcon}>{WORK_TYPE_ICON[entry.workType]}</Text>
        <View style={styles.cardHeaderText}>
          <Text style={styles.cardTitle} numberOfLines={1}>
            {entry.title || WORK_TYPE_LABELS[entry.workType]}
          </Text>
          <Text style={styles.cardDate}>
            {formatDate(entry.entryDate)}
            {entry.weather ? ` · ${WEATHER_LABELS[entry.weather] ?? entry.weather}` : ''}
            {entry.laborHours ? ` · ${entry.laborHours} giờ công` : ''}
          </Text>
        </View>
      </View>

      {entry.note ? (
        <Text style={styles.cardNote} numberOfLines={2}>
          {entry.note}
        </Text>
      ) : null}

      {usage && usage.lines.length > 0 && (
        <View style={styles.usageBox}>
          {usage.lines.map(line => (
            <Text key={line.name} style={styles.usageLine}>
              • {line.name}: {formatQuantity(line.quantity, line.unit)}
            </Text>
          ))}
          <Text style={styles.usageCost}>{formatMoney(usage.cost)}</Text>
        </View>
      )}
    </TouchableOpacity>
  );
}

interface Props {
  season: Season;
  entries: DiaryEntry[];
  onSelectEntry?: (entry: DiaryEntry) => void;
  onCreateEntry?: () => void;
}

export function DiaryListScreen({season, entries, onSelectEntry, onCreateEntry}: Props) {
  const [filter, setFilter] = useState<WorkType | null>(null);
  const [usages, setUsages] = useState<Map<string, UsageSummary>>(new Map());

  // Consumption is loaded for the whole page in one pass rather than per row:
  // 50 entries would otherwise be 50 round-trips to SQLite and the list would
  // stutter on a low-end phone.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (entries.length === 0) {
        setUsages(new Map());
        return;
      }
      const txns = await database
        .get<StockTransaction>('stock_transactions')
        .query(Q.where('diary_entry_id', Q.oneOf(entries.map(e => e.id))))
        .fetch();

      const supplyIds = [...new Set(txns.map(t => t.supplyId))];
      const supplies = await database
        .get('supplies')
        .query(Q.where('id', Q.oneOf(supplyIds)))
        .fetch();
      const supplyById = new Map(
        supplies.map(s => [s.id, s as unknown as {name: string; unit: string}]),
      );

      const grouped = new Map<string, UsageSummary>();
      for (const txn of txns) {
        if (!txn.diaryEntryId) {
          continue;
        }
        const entryUsage = grouped.get(txn.diaryEntryId) ?? {cost: 0, lines: []};
        const supply = supplyById.get(txn.supplyId);
        entryUsage.cost += txn.totalCost;
        entryUsage.lines.push({
          name: supply?.name ?? 'Vật tư',
          quantity: txn.quantity,
          unit: supply?.unit ?? '',
        });
        grouped.set(txn.diaryEntryId, entryUsage);
      }
      if (!cancelled) {
        setUsages(grouped);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [entries]);

  const visible = filter ? entries.filter(e => e.workType === filter) : entries;
  const presentTypes = [...new Set(entries.map(e => e.workType))];

  const handleSelect = useCallback(
    (entry: DiaryEntry) => onSelectEntry?.(entry),
    [onSelectEntry],
  );

  return (
    <View style={styles.container}>
      <View style={styles.seasonBar}>
        <Text style={styles.seasonName} numberOfLines={1}>
          {season.name}
        </Text>
        <Text style={styles.seasonCrop}>{season.cropType}</Text>
      </View>

      {presentTypes.length > 1 && (
        <View style={styles.filterRow}>
          <TouchableOpacity
            style={[styles.filterChip, filter === null && styles.filterChipActive]}
            onPress={() => setFilter(null)}>
            <Text
              style={[styles.filterText, filter === null && styles.filterTextActive]}>
              Tất cả
            </Text>
          </TouchableOpacity>
          {presentTypes.map(type => (
            <TouchableOpacity
              key={type}
              style={[styles.filterChip, filter === type && styles.filterChipActive]}
              onPress={() => setFilter(filter === type ? null : type)}>
              <Text
                style={[styles.filterText, filter === type && styles.filterTextActive]}>
                {WORK_TYPE_ICON[type]} {WORK_TYPE_LABELS[type]}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      )}

      <FlatList
        data={visible}
        keyExtractor={e => e.id}
        renderItem={({item}) => (
          <EntryCard entry={item} usage={usages.get(item.id)} onPress={handleSelect} />
        )}
        contentContainerStyle={
          visible.length === 0 ? styles.listEmpty : styles.listContent
        }
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyIcon}>📔</Text>
            <Text style={styles.emptyTitle}>
              {filter ? 'Không có nhật ký loại này' : 'Chưa có nhật ký nào'}
            </Text>
            <Text style={styles.emptyText}>
              Ghi lại công việc ngay khi làm xong — kể cả khi không có mạng.
            </Text>
          </View>
        }
        initialNumToRender={10}
        maxToRenderPerBatch={10}
        windowSize={7}
        removeClippedSubviews
      />

      <TouchableOpacity
        style={styles.fab}
        onPress={onCreateEntry}
        accessibilityRole="button"
        accessibilityLabel="Ghi nhật ký mới">
        <Text style={styles.fabText}>+</Text>
      </TouchableOpacity>
    </View>
  );
}

const enhance = withObservables(['seasonId'], ({seasonId}: {seasonId: string}) => ({
  season: database.get<Season>('seasons').findAndObserve(seasonId),
  entries: database
    .get<DiaryEntry>('diary_entries')
    .query(Q.where('season_id', seasonId), Q.sortBy('entry_date', Q.desc))
    .observeWithColumns(['work_type', 'entry_date', 'title', 'note', 'weather']),
}));

export default enhance(DiaryListScreen);

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: colors.background},

  seasonBar: {
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  seasonName: {...typography.label, color: colors.text},
  seasonCrop: {...typography.caption, color: colors.textSecondary},

  filterRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    paddingHorizontal: spacing.md,
    paddingTop: spacing.sm,
  },
  filterChip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    marginRight: spacing.xs,
    marginBottom: spacing.xs,
  },
  filterChipActive: {backgroundColor: colors.primary, borderColor: colors.primary},
  filterText: {...typography.caption, color: colors.textSecondary},
  filterTextActive: {color: colors.textOnPrimary, fontWeight: '600'},

  listContent: {padding: spacing.md, paddingBottom: 96},
  listEmpty: {flexGrow: 1},

  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  cardHeader: {flexDirection: 'row', alignItems: 'center'},
  cardIcon: {fontSize: 28, marginRight: spacing.sm},
  cardHeaderText: {flex: 1},
  cardTitle: {...typography.heading, color: colors.text},
  cardDate: {...typography.caption, color: colors.textSecondary, marginTop: 2},
  cardNote: {...typography.body, color: colors.textSecondary, marginTop: spacing.sm},

  usageBox: {
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  usageLine: {...typography.caption, color: colors.text, lineHeight: 20},
  usageCost: {...typography.label, color: colors.primary, marginTop: spacing.xs},

  empty: {flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.lg},
  emptyIcon: {fontSize: 56},
  emptyTitle: {...typography.heading, color: colors.text, marginTop: spacing.md},
  emptyText: {
    ...typography.body,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: spacing.sm,
    lineHeight: 22,
  },

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
