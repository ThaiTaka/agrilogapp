/**
 * Diary tab stack (Issues #20, #22).
 *
 *   SeasonList ──tap──▶ DiaryList ──tap──▶ DiaryForm
 *        │                   │
 *        └──"+"──▶ SeasonForm└──"Sửa mùa vụ"──▶ SeasonForm
 *
 * Tapping a season opens its DIARY, not its edit form. Editing a season is
 * rare — it happens once when it is created and maybe once when it closes —
 * while writing today's entry is the thing the farmer opens the app to do.
 * Putting the rare action behind the header and the common one on the card
 * follows from that, not from what is easier to wire.
 */

import {createNativeStackNavigator} from '@react-navigation/native-stack';
import type {NativeStackScreenProps} from '@react-navigation/native-stack';
import {Q} from '@nozbe/watermelondb';
import React from 'react';
import {StyleSheet, Text, TouchableOpacity} from 'react-native';

import {database} from '../db';
import type {DiaryEntry, Season, StockTransaction} from '../db/models';
import DiaryFormScreen from '../screens/diary/DiaryFormScreen';
import DiaryListScreen from '../screens/diary/DiaryListScreen';
import SeasonFormScreen from '../screens/seasons/SeasonFormScreen';
import SeasonListScreen from '../screens/seasons/SeasonListScreen';
import {colors, spacing, typography} from '../theme';

export type DiaryStackParamList = {
  SeasonList: undefined;
  SeasonForm: {seasonId?: string};
  DiaryList: {seasonId: string};
  DiaryForm: {seasonId: string; entryId?: string};
};

const Stack = createNativeStackNavigator<DiaryStackParamList>();

type ListProps = NativeStackScreenProps<DiaryStackParamList, 'SeasonList'>;
type SeasonFormProps = NativeStackScreenProps<DiaryStackParamList, 'SeasonForm'>;
type DiaryListProps = NativeStackScreenProps<DiaryStackParamList, 'DiaryList'>;
type DiaryFormProps = NativeStackScreenProps<DiaryStackParamList, 'DiaryForm'>;

function SeasonListRoute({navigation}: ListProps) {
  return (
    <SeasonListScreen
      onCreateSeason={() => navigation.navigate('SeasonForm', {})}
      onSelectSeason={(season: Season) =>
        navigation.navigate('DiaryList', {seasonId: season.id})
      }
    />
  );
}

function SeasonFormRoute({route, navigation}: SeasonFormProps) {
  const {seasonId} = route.params ?? {};
  const [season, setSeason] = React.useState<Season | undefined>();
  const [loading, setLoading] = React.useState(Boolean(seasonId));

  React.useEffect(() => {
    let cancelled = false;
    if (!seasonId) {
      setLoading(false);
      return;
    }
    database
      .get<Season>('seasons')
      .find(seasonId)
      .then(found => {
        if (!cancelled) {
          setSeason(found);
          setLoading(false);
        }
      })
      .catch(() => {
        // Deleted on another device and the tombstone arrived while this
        // screen was open. Going back is the honest response.
        if (!cancelled) {
          navigation.goBack();
        }
      });
    return () => {
      cancelled = true;
    };
  }, [seasonId, navigation]);

  if (loading) {
    return null;
  }

  return (
    <SeasonFormScreen
      season={season}
      onSaved={() => navigation.goBack()}
      // A deleted season's diary list is gone too, so pop all the way out.
      onDeleted={() => navigation.navigate('SeasonList')}
      onCancel={() => navigation.goBack()}
    />
  );
}

/** Declared at module scope so the header does not remount on every render. */
function EditSeasonButton({onPress}: {onPress: () => void}) {
  return (
    <TouchableOpacity onPress={onPress} hitSlop={{top: 12, bottom: 12, left: 12, right: 12}}>
      <Text style={styles.headerAction}>Sửa mùa vụ</Text>
    </TouchableOpacity>
  );
}

function DiaryListRoute({route, navigation}: DiaryListProps) {
  const {seasonId} = route.params;

  React.useLayoutEffect(() => {
    const renderEditButton = () => (
      <EditSeasonButton onPress={() => navigation.navigate('SeasonForm', {seasonId})} />
    );
    navigation.setOptions({headerRight: renderEditButton});
  }, [navigation, seasonId]);

  return (
    <DiaryListScreen
      seasonId={seasonId}
      onCreateEntry={() => navigation.navigate('DiaryForm', {seasonId})}
      onSelectEntry={(entry: DiaryEntry) =>
        navigation.navigate('DiaryForm', {seasonId, entryId: entry.id})
      }
    />
  );
}

function DiaryFormRoute({route, navigation}: DiaryFormProps) {
  const {seasonId, entryId} = route.params;
  const [entry, setEntry] = React.useState<DiaryEntry | undefined>();
  const [usages, setUsages] = React.useState<StockTransaction[]>([]);
  const [loading, setLoading] = React.useState(Boolean(entryId));

  React.useEffect(() => {
    let cancelled = false;
    if (!entryId) {
      setLoading(false);
      return;
    }
    (async () => {
      try {
        const found = await database.get<DiaryEntry>('diary_entries').find(entryId);
        const rows = await database
          .get<StockTransaction>('stock_transactions')
          .query(Q.where('diary_entry_id', entryId))
          .fetch();
        if (!cancelled) {
          setEntry(found);
          setUsages(rows);
          setLoading(false);
        }
      } catch {
        if (!cancelled) {
          navigation.goBack();
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [entryId, navigation]);

  if (loading) {
    return null;
  }

  return (
    <DiaryFormScreen
      seasonId={seasonId}
      entry={entry}
      existingUsages={usages}
      onSaved={() => navigation.goBack()}
      onDeleted={() => navigation.goBack()}
      onCancel={() => navigation.goBack()}
    />
  );
}

export default function DiaryStack() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: {backgroundColor: colors.primary},
        headerTintColor: colors.textOnPrimary,
        headerTitleStyle: {fontWeight: '700'},
      }}>
      <Stack.Screen
        name="SeasonList"
        component={SeasonListRoute}
        options={{title: 'Mùa vụ'}}
      />
      <Stack.Screen
        name="SeasonForm"
        component={SeasonFormRoute}
        options={({route}) => ({
          title: route.params?.seasonId ? 'Sửa mùa vụ' : 'Mùa vụ mới',
        })}
      />
      <Stack.Screen
        name="DiaryList"
        component={DiaryListRoute}
        options={{title: 'Nhật ký'}}
      />
      <Stack.Screen
        name="DiaryForm"
        component={DiaryFormRoute}
        options={({route}) => ({
          title: route.params?.entryId ? 'Sửa nhật ký' : 'Ghi nhật ký',
        })}
      />
    </Stack.Navigator>
  );
}

const styles = StyleSheet.create({
  headerAction: {
    ...typography.label,
    color: colors.textOnPrimary,
    paddingHorizontal: spacing.sm,
  },
});
