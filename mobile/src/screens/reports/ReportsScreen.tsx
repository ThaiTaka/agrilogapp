/**
 * Ba biểu đồ báo cáo (Issues #43–#47).
 *
 * Every number here is computed from local WatermelonDB, so the whole screen
 * renders in airplane mode. That is the acceptance bar for Issue #47, and it
 * is why the reducers live in services/reports.ts rather than being fetched.
 *
 * Chart choices follow from the question each one answers:
 *   1. line   — "am I spending faster than I'm earning?" is about a TREND
 *   2. pie    — "which input eats my budget?" is about SHARE of a whole
 *   3. bar    — "which season did best?" is about COMPARING magnitudes
 */

import {useFocusEffect} from '@react-navigation/native';
import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {
  ActivityIndicator,
  Dimensions,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import {BarChart, LineChart, PieChart} from 'react-native-chart-kit';

import {database} from '../../db';
import type {Season} from '../../db/models';
import {
  incomeExpenseReport,
  seasonComparisonReport,
  supplyConsumptionReport,
  type Granularity,
  type IncomeExpenseReport,
  type SeasonComparisonReport,
  type SupplyConsumptionReport,
} from '../../services/reports';
import {observeSeasons} from '../../services/seasons';
import {colors, radius, shadows, spacing, typography} from '../../theme';
import {formatMoney, formatMoneyShort} from '../../utils/numeric';

const SCREEN_WIDTH = Dimensions.get('window').width;
const CHART_WIDTH = SCREEN_WIDTH - spacing.md * 2;

/** Categorical palette — distinguishable in sunlight and to colour-blind eyes. */
const SLICE_COLORS = [
  '#2E7D32',
  '#F57C00',
  '#0277BD',
  '#8E24AA',
  '#C62828',
  '#00838F',
  '#6D4C41',
];

const chartConfig = {
  backgroundGradientFrom: colors.surface,
  backgroundGradientTo: colors.surface,
  decimalPlaces: 0,
  color: (opacity = 1) => `rgba(46, 125, 50, ${opacity})`,
  labelColor: (opacity = 1) => `rgba(90, 90, 90, ${opacity})`,
  propsForDots: {r: '4'},
  propsForBackgroundLines: {stroke: colors.border},
  // Raw VND runs to nine digits and would overflow the axis gutter. BarChart
  // takes this through chartConfig only — unlike LineChart it has no
  // `formatYLabel` prop of its own.
  formatYLabel: (value: string) => formatMoneyShort(Number(value)),
};

function Section({title, subtitle, children}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      <Text style={styles.sectionSubtitle}>{subtitle}</Text>
      {children}
    </View>
  );
}

function NoData({message}: {message: string}) {
  return (
    <View style={styles.noData}>
      <Text style={styles.noDataText}>{message}</Text>
    </View>
  );
}

export default function ReportsScreen() {
  const [seasons, setSeasons] = useState<Season[]>([]);
  const [seasonId, setSeasonId] = useState<string | null>(null);
  const [granularity, setGranularity] = useState<Granularity>('month');

  const [incomeExpense, setIncomeExpense] = useState<IncomeExpenseReport | null>(null);
  const [consumption, setConsumption] = useState<SupplyConsumptionReport | null>(null);
  const [comparison, setComparison] = useState<SeasonComparisonReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const sub = observeSeasons(database).subscribe(rows => {
      setSeasons(rows);
      // Keep the current selection only if it still exists. Holding a deleted
      // season's id left every chart empty with no way back but restarting.
      setSeasonId(current =>
        current && rows.some(s => s.id === current) ? current : (rows[0]?.id ?? null),
      );
    });
    return () => sub.unsubscribe();
  }, []);

  /** Invalidates in-flight loads, so a stale result cannot overwrite a newer one. */
  const runId = useRef(0);

  const load = useCallback(async () => {
    const ticket = ++runId.current;
    setLoading(true);
    const [cmp, cons, ie] = await Promise.all([
      seasonComparisonReport(database),
      seasonId ? supplyConsumptionReport(database, {seasonId}) : Promise.resolve(null),
      seasonId ? incomeExpenseReport(database, seasonId, granularity) : Promise.resolve(null),
    ]);
    // Superseded — the season was switched, or the screen left — while these
    // three reducers were running over the local database.
    if (ticket !== runId.current) {
      return;
    }
    setComparison(cmp);
    setConsumption(cons);
    setIncomeExpense(ie);
    setLoading(false);
  }, [seasonId, granularity]);

  /**
   * Reloaded on focus, not once on mount.
   *
   * This screen is a tab, so it stays mounted after the first visit. Recording
   * an expense or a diary entry in another tab and coming back here showed
   * charts drawn from data that no longer existed, and nothing on screen said
   * so — the numbers simply disagreed with the Thu chi tab.
   */
  useFocusEffect(
    useCallback(() => {
      load();
      return () => {
        runId.current += 1;
      };
    }, [load]),
  );

  // Chart-kit renders every label, so a 90-day season would produce an
  // unreadable smear. Thin the labels, never the data.
  const lineData = useMemo(() => {
    if (!incomeExpense || incomeExpense.buckets.length === 0) {
      return null;
    }
    const buckets = incomeExpense.buckets;
    const step = Math.max(1, Math.ceil(buckets.length / 6));
    return {
      labels: buckets.map((b, i) => (i % step === 0 ? b.period.slice(2) : '')),
      datasets: [
        {
          data: buckets.map(b => b.revenue),
          color: (o = 1) => `rgba(46, 125, 50, ${o})`,
          strokeWidth: 2,
        },
        {
          data: buckets.map(b => b.expense),
          color: (o = 1) => `rgba(198, 40, 40, ${o})`,
          strokeWidth: 2,
        },
      ],
      legend: ['Thu', 'Chi'],
    };
  }, [incomeExpense]);

  const pieData = useMemo(() => {
    if (!consumption || consumption.items.length === 0) {
      return null;
    }
    return consumption.items.map((item, index) => ({
      name: item.label,
      cost: item.totalCost,
      color: SLICE_COLORS[index % SLICE_COLORS.length]!,
      legendFontColor: colors.textSecondary,
      legendFontSize: 12,
    }));
  }, [consumption]);

  const barData = useMemo(() => {
    if (!comparison || comparison.seasons.length === 0) {
      return null;
    }
    // Oldest first: a comparison chart reads left-to-right as time passing.
    const ordered = [...comparison.seasons].sort((a, b) => a.startDate - b.startDate);
    return {
      labels: ordered.map(s => (s.name.length > 10 ? `${s.name.slice(0, 9)}…` : s.name)),
      datasets: [{data: ordered.map(s => s.profit)}],
    };
  }, [comparison]);

  if (seasons.length === 0) {
    return (
      <View style={styles.container}>
        <View style={styles.empty}>
          <Text style={styles.emptyIcon}>📊</Text>
          <Text style={styles.emptyTitle}>Chưa có dữ liệu</Text>
          <Text style={styles.emptyText}>
            Tạo mùa vụ và ghi nhật ký, thu chi — biểu đồ sẽ xuất hiện ở đây.
          </Text>
        </View>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}>
      {seasons.length > 1 && (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.picker}
          contentContainerStyle={styles.pickerContent}>
          {seasons.map(s => (
            <TouchableOpacity
              key={s.id}
              style={[styles.chip, seasonId === s.id && styles.chipActive]}
              onPress={() => setSeasonId(s.id)}>
              <Text
                style={[styles.chipText, seasonId === s.id && styles.chipTextActive]}
                numberOfLines={1}>
                {s.name}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      )}

      {/* ── Biểu đồ 1 ─────────────────────────────────────────────────── */}
      <Section
        title="Thu chi theo thời gian"
        subtitle="Tôi có đang tiêu nhanh hơn kiếm không?">
        <View style={styles.granularityRow}>
          {(['day', 'week', 'month'] as Granularity[]).map(g => (
            <TouchableOpacity
              key={g}
              style={[styles.smallChip, granularity === g && styles.chipActive]}
              onPress={() => setGranularity(g)}>
              <Text
                style={[styles.chipText, granularity === g && styles.chipTextActive]}>
                {g === 'day' ? 'Ngày' : g === 'week' ? 'Tuần' : 'Tháng'}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {lineData ? (
          <>
            <LineChart
              data={lineData}
              width={CHART_WIDTH}
              height={220}
              chartConfig={chartConfig}
              formatYLabel={value => formatMoneyShort(Number(value))}
              bezier
              style={styles.chart}
            />
            {incomeExpense && (
              <View style={styles.totalsRow}>
                <Text style={styles.totalRevenue}>
                  Thu {formatMoney(incomeExpense.totals.revenue)}
                </Text>
                <Text style={styles.totalExpense}>
                  Chi {formatMoney(incomeExpense.totals.expense)}
                </Text>
                <Text
                  style={[
                    styles.totalProfit,
                    incomeExpense.totals.profit < 0 && styles.lossColor,
                  ]}>
                  Lãi {formatMoney(incomeExpense.totals.profit)}
                </Text>
              </View>
            )}
          </>
        ) : loading ? (
          <ActivityIndicator color={colors.primary} style={styles.loading} />
        ) : (
          <NoData message="Chưa có thu chi nào trong mùa vụ này." />
        )}
      </Section>

      {/* ── Biểu đồ 2 ─────────────────────────────────────────────────── */}
      <Section
        title="Vật tư tiêu thụ"
        subtitle="Loại vật tư nào đang ngốn tiền nhất?">
        {pieData ? (
          <>
            <PieChart
              data={pieData}
              width={CHART_WIDTH}
              height={200}
              chartConfig={chartConfig}
              accessor="cost"
              backgroundColor="transparent"
              paddingLeft="8"
              absolute={false}
            />
            {/*
              Plotted by COST, never by quantity. When a group mixes units —
              phân bón in both kg and bao — adding the quantities produces a
              number with no meaning, so cost is the only honest measure.
            */}
            {consumption?.items.some(i => i.unitMixed) && (
              <Text style={styles.note}>
                Biểu đồ theo chi phí vì có nhóm gộp nhiều đơn vị khác nhau.
              </Text>
            )}
            <View style={styles.legend}>
              {consumption?.items.map((item, index) => (
                <View key={item.key} style={styles.legendRow}>
                  <View
                    style={[
                      styles.legendDot,
                      {backgroundColor: SLICE_COLORS[index % SLICE_COLORS.length]},
                    ]}
                  />
                  <Text style={styles.legendLabel} numberOfLines={1}>
                    {item.label}
                  </Text>
                  <Text style={styles.legendValue}>
                    {formatMoney(item.totalCost)} · {item.sharePct}%
                  </Text>
                </View>
              ))}
            </View>
          </>
        ) : loading ? (
          <ActivityIndicator color={colors.primary} style={styles.loading} />
        ) : (
          <NoData message="Chưa ghi lượng vật tư nào trong mùa vụ này." />
        )}
      </Section>

      {/* ── Biểu đồ 3 ─────────────────────────────────────────────────── */}
      <Section
        title="So sánh lợi nhuận mùa vụ"
        subtitle="Mùa vụ nào thực sự hiệu quả nhất?">
        {barData ? (
          <>
            <BarChart
              data={barData}
              width={CHART_WIDTH}
              height={220}
              chartConfig={chartConfig}
              yAxisLabel=""
              yAxisSuffix=""
              fromZero
              showValuesOnTopOfBars={false}
              style={styles.chart}
            />
            {comparison?.seasons.map(s => (
              <View key={s.seasonId} style={styles.comparisonRow}>
                <Text style={styles.comparisonName} numberOfLines={1}>
                  {s.seasonId === comparison.bestSeasonId ? '🏆 ' : ''}
                  {s.name}
                </Text>
                <Text
                  style={[
                    styles.comparisonProfit,
                    s.profit < 0 && styles.lossColor,
                  ]}>
                  {formatMoney(s.profit)}
                  {s.marginPct !== null ? ` · ${s.marginPct}%` : ''}
                </Text>
              </View>
            ))}
          </>
        ) : loading ? (
          <ActivityIndicator color={colors.primary} style={styles.loading} />
        ) : (
          <NoData message="Chưa có mùa vụ nào để so sánh." />
        )}
      </Section>

      <Text style={styles.footer}>
        Mọi số liệu tính từ dữ liệu trên máy — xem được cả khi không có mạng.
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: colors.background},
  content: {padding: spacing.md, paddingBottom: spacing.xl},

  picker: {marginBottom: spacing.md},
  pickerContent: {paddingRight: spacing.md},
  chip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    marginRight: spacing.xs,
    maxWidth: 200,
  },
  smallChip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    marginRight: spacing.xs,
  },
  chipActive: {backgroundColor: colors.primary, borderColor: colors.primary},
  chipText: {...typography.caption, color: colors.textSecondary},
  chipTextActive: {color: colors.textOnPrimary, fontWeight: '600'},

  section: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginBottom: spacing.ms,
    ...shadows.card,
  },
  sectionTitle: {...typography.heading, color: colors.text},
  sectionSubtitle: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: 2,
    marginBottom: spacing.sm,
    fontStyle: 'italic',
  },
  granularityRow: {flexDirection: 'row', marginBottom: spacing.sm},
  chart: {borderRadius: radius.md, marginLeft: -spacing.sm},
  loading: {marginVertical: spacing.xl},

  noData: {paddingVertical: spacing.xl, alignItems: 'center'},
  noDataText: {...typography.body, color: colors.textSecondary, textAlign: 'center'},
  note: {...typography.caption, color: colors.textSecondary, marginTop: spacing.xs},

  totalsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  totalRevenue: {...typography.caption, color: colors.success, fontWeight: '600'},
  totalExpense: {...typography.caption, color: colors.danger, fontWeight: '600'},
  totalProfit: {...typography.caption, color: colors.primaryDark, fontWeight: '700'},
  lossColor: {color: colors.danger},

  legend: {marginTop: spacing.sm},
  legendRow: {flexDirection: 'row', alignItems: 'center', paddingVertical: spacing.xs},
  legendDot: {width: 10, height: 10, borderRadius: 5, marginRight: spacing.sm},
  legendLabel: {...typography.caption, color: colors.text, flex: 1},
  legendValue: {...typography.caption, color: colors.textSecondary},

  comparisonRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: spacing.xs,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  comparisonName: {...typography.caption, color: colors.text, flex: 1},
  comparisonProfit: {...typography.caption, color: colors.primaryDark, fontWeight: '600'},

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

  footer: {
    ...typography.caption,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: spacing.sm,
  },
});
