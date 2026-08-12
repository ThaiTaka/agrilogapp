/**
 * Diary tab stack: season list → create/edit season.
 *
 * Seasons live under the Diary tab rather than getting a tab of their own
 * because a farmer does not think about "seasons" as a destination — they
 * think "I need to write down what I did today", and the season is the folder
 * that lands in. Diary entry screens (Issue #22) nest one level deeper.
 */

import {createNativeStackNavigator} from '@react-navigation/native-stack';
import type {NativeStackScreenProps} from '@react-navigation/native-stack';
import React from 'react';

import {database} from '../db';
import type {Season} from '../db/models';
import SeasonFormScreen from '../screens/seasons/SeasonFormScreen';
import SeasonListScreen from '../screens/seasons/SeasonListScreen';
import {colors} from '../theme';

export type DiaryStackParamList = {
  SeasonList: undefined;
  SeasonForm: {seasonId?: string};
};

const Stack = createNativeStackNavigator<DiaryStackParamList>();

type ListProps = NativeStackScreenProps<DiaryStackParamList, 'SeasonList'>;
type FormProps = NativeStackScreenProps<DiaryStackParamList, 'SeasonForm'>;

function SeasonListRoute({navigation}: ListProps) {
  return (
    <SeasonListScreen
      onCreateSeason={() => navigation.navigate('SeasonForm', {})}
      onSelectSeason={(season: Season) =>
        navigation.navigate('SeasonForm', {seasonId: season.id})
      }
    />
  );
}

function SeasonFormRoute({route, navigation}: FormProps) {
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
        // The season was deleted on another device and the tombstone arrived
        // while this screen was open. Going back is the honest response.
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
    </Stack.Navigator>
  );
}
