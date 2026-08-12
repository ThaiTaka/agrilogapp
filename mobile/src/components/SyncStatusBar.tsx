/**
 * Sync status indicator (Issue #35).
 *
 * Answers three questions a farmer actually has, in one line:
 *   - is my work saved?          (always yes — that is the point)
 *   - has it reached the server? (pending count)
 *   - when did it last reach it? (relative time)
 *
 * The wording is chosen carefully. Pending changes are never framed as an
 * error or a warning: being offline is the NORMAL state in a field, and an app
 * that looks broken every time it loses signal is an app that gets distrusted
 * and then abandoned. "5 thay đổi chờ gửi" is a status; "Lỗi đồng bộ" is not
 * what is happening.
 */

import React, {useCallback, useEffect, useState} from 'react';
import {ActivityIndicator, StyleSheet, Text, TouchableOpacity, View} from 'react-native';

import {colors, MIN_TOUCH_TARGET, radius, spacing, typography} from '../theme';
import {getLastSyncAt, pendingChangeCount, sync, type RejectedRecord} from '../services/sync';

function relativeTime(ms: number | null): string {
  if (!ms) {
    return 'chưa đồng bộ lần nào';
  }
  const seconds = Math.floor((Date.now() - ms) / 1000);
  if (seconds < 60) {
    return 'vừa xong';
  }
  if (seconds < 3600) {
    return `${Math.floor(seconds / 60)} phút trước`;
  }
  if (seconds < 86400) {
    return `${Math.floor(seconds / 3600)} giờ trước`;
  }
  return `${Math.floor(seconds / 86400)} ngày trước`;
}

export interface SyncStatusBarProps {
  /** How often to refresh the pending count while visible. */
  pollMs?: number;
  onRejections?: (rejections: RejectedRecord[]) => void;
}

export default function SyncStatusBar({pollMs = 5_000, onRejections}: SyncStatusBarProps) {
  const [pending, setPending] = useState(0);
  const [lastSync, setLastSync] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [count, last] = await Promise.all([pendingChangeCount(), getLastSyncAt()]);
    setPending(count);
    setLastSync(last);
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, pollMs);
    return () => clearInterval(timer);
  }, [refresh, pollMs]);

  const onSyncNow = useCallback(async () => {
    setBusy(true);
    setMessage(null);
    try {
      const result = await sync();
      if (result.ok) {
        setMessage(
          result.pushed > 0 ? `Đã gửi ${result.pushed} thay đổi` : 'Đã cập nhật',
        );
      } else {
        // Reassurance first. Nothing was lost; every record is still in
        // SQLite and will go up next time.
        setMessage('Chưa gửi được — dữ liệu vẫn an toàn trên máy');
      }
      if (result.rejected.length > 0) {
        onRejections?.(result.rejected);
      }
    } finally {
      setBusy(false);
      await refresh();
    }
  }, [refresh, onRejections]);

  const hasPending = pending > 0;

  return (
    <View style={[styles.bar, hasPending ? styles.barPending : styles.barSynced]}>
      <View style={styles.info}>
        <View style={[styles.dot, hasPending ? styles.dotPending : styles.dotSynced]} />
        <View style={styles.textBlock}>
          <Text style={styles.status} numberOfLines={1}>
            {hasPending ? `${pending} thay đổi chờ gửi` : 'Đã đồng bộ'}
          </Text>
          <Text style={styles.subtext} numberOfLines={1}>
            {message ?? `Lần cuối: ${relativeTime(lastSync)}`}
          </Text>
        </View>
      </View>

      <TouchableOpacity
        style={styles.button}
        onPress={onSyncNow}
        disabled={busy}
        accessibilityRole="button"
        accessibilityLabel="Đồng bộ ngay">
        {busy ? (
          <ActivityIndicator size="small" color={colors.primary} />
        ) : (
          <Text style={styles.buttonText}>Đồng bộ</Text>
        )}
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  barSynced: {backgroundColor: '#E8F5E9'},
  barPending: {backgroundColor: '#FFF3E0'},
  info: {flexDirection: 'row', alignItems: 'center', flex: 1},
  dot: {width: 10, height: 10, borderRadius: 5, marginRight: spacing.sm},
  dotSynced: {backgroundColor: colors.synced},
  dotPending: {backgroundColor: colors.pending},
  textBlock: {flex: 1},
  status: {...typography.label, color: colors.text},
  subtext: {...typography.caption, color: colors.textSecondary},
  button: {
    minHeight: MIN_TOUCH_TARGET - 12,
    minWidth: 88,
    paddingHorizontal: spacing.md,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.primary,
  },
  buttonText: {...typography.label, color: colors.primary},
});
