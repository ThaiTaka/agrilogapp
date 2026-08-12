/**
 * Navigation shell (Issue #17).
 *
 * Two stacks selected by auth state: signed out shows only the login screen,
 * signed in shows the four modules from the proposal. Auth is read from
 * storage at launch with no network call, so opening the app in a field with
 * no signal lands on the tabs, not on a login form.
 */

import {NavigationContainer} from '@react-navigation/native';
import {createBottomTabNavigator} from '@react-navigation/bottom-tabs';
import {createNativeStackNavigator} from '@react-navigation/native-stack';
import React from 'react';
import {ActivityIndicator, StyleSheet, Text, View} from 'react-native';

import LoginScreen from '../screens/auth/LoginScreen';
import ReportsScreen from '../screens/reports/ReportsScreen';
import DiaryStack from './DiaryStack';
import FinanceStack from './FinanceStack';
import SuppliesStack from './SuppliesStack';
import {useAuth} from '../services/auth';
import {colors, spacing, typography} from '../theme';

export type RootStackParamList = {
  Login: undefined;
  Main: undefined;
};

export type MainTabParamList = {
  Diary: undefined;
  Supplies: undefined;
  Finance: undefined;
  Reports: undefined;
};

const RootStack = createNativeStackNavigator<RootStackParamList>();
const Tab = createBottomTabNavigator<MainTabParamList>();

// Emoji instead of a vector-icon dependency: it renders identically on every
// Android version without a font-linking step, and these four are
// unambiguous. Swap for react-native-vector-icons if the set ever grows.
const TAB_ICON: Record<keyof MainTabParamList, string> = {
  Diary: '📔',
  Supplies: '📦',
  Finance: '💰',
  Reports: '📊',
};

function TabIcon({name, focused}: {name: keyof MainTabParamList; focused: boolean}) {
  return (
    <Text style={focused ? styles.tabIconActive : styles.tabIcon}>{TAB_ICON[name]}</Text>
  );
}

/**
 * Built once per route, outside render, so React Navigation does not see a
 * new component type on every render and tear down the tab's subtree.
 */
const tabIconRenderers: Record<
  keyof MainTabParamList,
  (props: {focused: boolean}) => React.ReactElement
> = {
  Diary: ({focused}) => <TabIcon name="Diary" focused={focused} />,
  Supplies: ({focused}) => <TabIcon name="Supplies" focused={focused} />,
  Finance: ({focused}) => <TabIcon name="Finance" focused={focused} />,
  Reports: ({focused}) => <TabIcon name="Reports" focused={focused} />,
};

// Season management is live (#20). Diary entry screens (#22) nest inside it.

// Supplies is live (#24) — see SuppliesStack.

// Finance is live (#28) — see FinanceStack.

// Reports are live (#43–#47) — see screens/reports/ReportsScreen.

function MainTabs() {
  return (
    <Tab.Navigator
      screenOptions={({route}) => ({
        headerStyle: {backgroundColor: colors.primary},
        headerTintColor: colors.textOnPrimary,
        headerTitleStyle: {fontWeight: '700'},
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textSecondary,
        // 60dp: comfortably above the 48dp minimum, because this bar gets
        // tapped with a thumb that has just been in soil.
        tabBarStyle: {height: 60, paddingBottom: 6, paddingTop: 6},
        tabBarLabelStyle: {fontSize: 12, fontWeight: '600'},
        tabBarIcon: tabIconRenderers[route.name],
      })}>
      <Tab.Screen
        name="Diary"
        component={DiaryStack}
        // The stack draws its own header, so the tab navigator must not.
        options={{title: 'Nhật ký', headerShown: false}}
      />
      <Tab.Screen
        name="Supplies"
        component={SuppliesStack}
        options={{title: 'Vật tư', headerShown: false}}
      />
      <Tab.Screen
        name="Finance"
        component={FinanceStack}
        options={{title: 'Thu chi', headerShown: false}}
      />
      <Tab.Screen
        name="Reports"
        component={ReportsScreen}
        options={{title: 'Báo cáo'}}
      />
    </Tab.Navigator>
  );
}

function SplashScreen() {
  return (
    <View style={styles.splash}>
      <Text style={styles.splashLogo}>🌾</Text>
      <Text style={styles.splashTitle}>AgriLog</Text>
      <ActivityIndicator color={colors.primary} style={{marginTop: spacing.lg}} />
    </View>
  );
}

export default function RootNavigator() {
  const {status} = useAuth();

  if (status === 'loading') {
    return <SplashScreen />;
  }

  return (
    <NavigationContainer>
      <RootStack.Navigator screenOptions={{headerShown: false}}>
        {status === 'signedIn' ? (
          <RootStack.Screen name="Main" component={MainTabs} />
        ) : (
          <RootStack.Screen name="Login" component={LoginScreen} />
        )}
      </RootStack.Navigator>
    </NavigationContainer>
  );
}

const styles = StyleSheet.create({
  splash: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
  },
  splashLogo: {fontSize: 72},
  splashTitle: {...typography.title, fontSize: 28, color: colors.primaryDark},
  tabIcon: {fontSize: 22},
  tabIconActive: {fontSize: 26},
});
