import React from 'react';
import {ScrollView, StyleSheet, Text, View} from 'react-native';

import {colors, radius, spacing, typography} from '../theme';

/**
 * Tab placeholder while each module is being built (Issue #17).
 *
 * Deliberately states which issue fills it in, rather than showing a generic
 * "Coming soon" — during a single-developer build the app itself is the
 * clearest progress board there is.
 */
export default function PlaceholderScreen({
  icon,
  title,
  description,
  issues,
}: {
  icon: string;
  title: string;
  description: string;
  issues: string[];
}) {
  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.icon}>{icon}</Text>
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.description}>{description}</Text>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Sẽ hoàn thiện ở</Text>
        {issues.map(issue => (
          <Text key={issue} style={styles.issue}>
            • {issue}
          </Text>
        ))}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flexGrow: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.lg,
    backgroundColor: colors.background,
  },
  icon: {fontSize: 64, marginBottom: spacing.md},
  title: {...typography.title, color: colors.text},
  description: {
    ...typography.body,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: spacing.sm,
    lineHeight: 22,
  },
  card: {
    marginTop: spacing.xl,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    alignSelf: 'stretch',
  },
  cardTitle: {...typography.label, color: colors.textSecondary, marginBottom: spacing.sm},
  issue: {...typography.body, color: colors.text, lineHeight: 24},
});
