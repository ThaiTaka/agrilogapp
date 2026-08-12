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
import PlaceholderScreen from '../screens/PlaceholderScreen';
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

function DiaryTab() {
  return (
    <PlaceholderScreen
      icon="📔"
      title="Nhật ký canh tác"
      description="Ghi lại công việc đồng ruộng theo từng mùa vụ: bón phân, phun thuốc, thu hoạch — kèm vật tư đã dùng."
      issues={['#20 Màn hình mùa vụ', '#22 Màn hình nhật ký', '#26 Hoàn kho ngoại tuyến']}
    />
  );
}

function SuppliesTab() {
  return (
    <PlaceholderScreen
      icon="📦"
      title="Vật tư"
      description="Danh mục vật tư, nhập kho, xuất kho và tồn kho thời gian thực — tính từ sổ cái, không lưu sẵn."
      issues={['#24 Màn hình kho vật tư']}
    />
  );
}

function FinanceTab() {
  return (
    <PlaceholderScreen
      icon="💰"
      title="Thu chi"
      description="Chi phí và doanh thu theo mùa vụ. Chi phí vật tư tự sinh từ nhật ký, không phải nhập tay hai lần."
      issues={['#28 Màn hình thu chi và tổng kết mùa vụ']}
    />
  );
}

function ReportsTab() {
  return (
    <PlaceholderScreen
      icon="📊"
      title="Báo cáo"
      description="Ba biểu đồ: thu chi theo thời gian, vật tư tiêu thụ, so sánh lợi nhuận giữa các mùa vụ."
      issues={[
        '#43 Tích hợp thư viện biểu đồ',
        '#44 Biểu đồ thu chi',
        '#45 Biểu đồ vật tư',
        '#46 Biểu đồ so sánh mùa vụ',
      ]}
    />
  );
}

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
      <Tab.Screen name="Diary" component={DiaryTab} options={{title: 'Nhật ký'}} />
      <Tab.Screen name="Supplies" component={SuppliesTab} options={{title: 'Vật tư'}} />
      <Tab.Screen name="Finance" component={FinanceTab} options={{title: 'Thu chi'}} />
      <Tab.Screen name="Reports" component={ReportsTab} options={{title: 'Báo cáo'}} />
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
