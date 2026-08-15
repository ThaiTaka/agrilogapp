/**
 * Danh sách mùa vụ (Issue #20).
 *
 * Reads from an observable WatermelonDB query, so it re-renders the instant a
 * write lands — including a write that arrives from another device through
 * sync. There is no refresh button and no pull-to-refresh, because there is
 * nothing to refresh from: the local database is the source of truth.
 */

import {withObservables} from '@nozbe/watermelondb/react';
import React, {useCallback} from 'react';
import {FlatList, StyleSheet, Text, TouchableOpacity, View} from 'react-native';

import SyncStatusBar from '../../components/SyncStatusBar';
import {database} from '../../db';
import {SEASON_STATUS_LABELS, SeasonStatus} from '../../db/enums';
import type {Season} from '../../db/models';
import {observeSeasons} from '../../services/seasons';
import {colors, MIN_TOUCH_TARGET, radius, shadows, spacing, typography} from '../../theme';
import {daysElapsed, formatDateRange} from '../../utils/date';
import {formatQuantity} from '../../utils/numeric';

const STATUS_COLORS: Record<SeasonStatus, string> = {
  planning: colors.info,
  active: colors.success,
  harvested: colors.accent,
  closed: colors.textSecondary,
};

function SeasonCard({season, onPress}: {season: Season; onPress: (s: Season) => void}) {
  const statusColor = STATUS_COLORS[season.status] ?? colors.textSecondary;

  return (
    <TouchableOpacity
      style={styles.card}
      onPress={() => onPress(season)}
      accessibilityRole="button">
      <View style={styles.cardHeader}>
        <Text style={styles.cardTitle} numberOfLines={1}>
          {season.name}
        </Text>
        <View style={[styles.badge, {backgroundColor: statusColor}]}>
          <Text style={styles.badgeText}>{SEASON_STATUS_LABELS[season.status]}</Text>
        </View>
      </View>

      <Text style={styles.cardCrop}>🌱 {season.cropType}</Text>

      <View style={styles.cardMeta}>
        <Text style={styles.cardMetaText}>
          {formatDateRange(season.startDate, season.endDate)}
        </Text>
        {season.areaSize !== null && (
          <Text style={styles.cardMetaText}>
            {formatQuantity(season.areaSize, season.areaUnit)}
          </Text>
        )}
      </View>

      {season.status === SeasonStatus.ACTIVE && (
        <Text style={styles.cardDays}>
          Đã canh tác {daysElapsed(season.startDate)} ngày
        </Text>
      )}
    </TouchableOpacity>
  );
}

function EmptyState({onCreate}: {onCreate: () => void}) {
  return (
    <View style={styles.empty}>
      <Text style={styles.emptyIcon}>🌾</Text>
      <Text style={styles.emptyTitle}>Chưa có mùa vụ nào</Text>
      <Text style={styles.emptyText}>
        Tạo mùa vụ đầu tiên để bắt đầu ghi nhật ký canh tác, theo dõi vật tư và
        tính chi phí.
      </Text>
      <TouchableOpacity style={styles.emptyButton} onPress={onCreate}>
        <Text style={styles.emptyButtonText}>Tạo mùa vụ</Text>
      </TouchableOpacity>
    </View>
  );
}

interface Props {
  seasons: Season[];
  onSelectSeason?: (season: Season) => void;
  onCreateSeason?: () => void;
}

export function SeasonListScreen({seasons, onSelectSeason, onCreateSeason}: Props) {
  const handleSelect = useCallback(
    (season: Season) => onSelectSeason?.(season),
    [onSelectSeason],
  );
  const handleCreate = useCallback(() => onCreateSeason?.(), [onCreateSeason]);

  return (
    <View style={styles.container}>
      <SyncStatusBar />

      <FlatList
        data={seasons}
        keyExtractor={s => s.id}
        renderItem={({item}) => <SeasonCard season={item} onPress={handleSelect} />}
        contentContainerStyle={
          seasons.length === 0 ? styles.listEmpty : styles.listContent
        }
        ListEmptyComponent={<EmptyState onCreate={handleCreate} />}
        // Virtualisation tuning for long lists on low-end phones (Issue #50).
        initialNumToRender={8}
        maxToRenderPerBatch={8}
        windowSize={7}
        removeClippedSubviews
      />

      {seasons.length > 0 && (
        <TouchableOpacity
          style={styles.fab}
          onPress={handleCreate}
          accessibilityRole="button"
          accessibilityLabel="Tạo mùa vụ mới">
          <Text style={styles.fabText}>+</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

/**
 * `observeWithColumns` rather than plain `observe`: the list must re-render
 * when a season's name or status changes, not only when one is added or
 * removed.
 */
const enhance = withObservables([], () => ({
  seasons: observeSeasons(database),
}));

export default enhance(SeasonListScreen);

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: colors.background},
  listContent: {padding: spacing.md, paddingBottom: 96},
  listEmpty: {flexGrow: 1},

  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginBottom: spacing.ms,
    ...shadows.card,
  },
  cardHeader: {flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between'},
  cardTitle: {...typography.heading, color: colors.text, flex: 1, marginRight: spacing.sm},
  badge: {paddingHorizontal: spacing.sm, paddingVertical: 2, borderRadius: radius.pill},
  badgeText: {...typography.caption, color: colors.textOnPrimary, fontWeight: '600'},
  cardCrop: {...typography.body, color: colors.textSecondary, marginTop: spacing.xs},
  cardMeta: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: spacing.sm,
  },
  cardMetaText: {...typography.caption, color: colors.textSecondary},
  cardDays: {...typography.caption, color: colors.primary, marginTop: spacing.xs},

  empty: {flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.lg},
  emptyIcon: {fontSize: 64},
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
    ...shadows.floating,
  },
  fabText: {fontSize: 32, color: colors.textOnPrimary, lineHeight: 36},
});
