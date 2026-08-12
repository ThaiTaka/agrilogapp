/**
 * AgriLog — ứng dụng quản lý nhật ký canh tác, vật tư và chi phí nông nghiệp.
 *
 * Đồ án tốt nghiệp — Khoa CNTT, Trường Đại học Đà Lạt.
 */

import 'react-native-gesture-handler';

import React from 'react';
import {StatusBar, StyleSheet, View} from 'react-native';
import {SafeAreaProvider} from 'react-native-safe-area-context';

import RootNavigator from './src/navigation';
import {AuthProvider} from './src/services/auth';
import {colors} from './src/theme';

// Imported for the side effect: it registers the UUID generator override
// (rule R1 — record IDs are created on the device) and opens the SQLite
// adapter, so the local database is ready before the first screen renders.
import './src/db';

export default function App() {
  return (
    <SafeAreaProvider>
      <View style={styles.root}>
        {/*
          No `backgroundColor`: React Native 0.87 removed the prop because
          Android is edge-to-edge by default. The bar colour comes from the
          native theme (android/app/src/main/res/values/styles.xml).
        */}
        <StatusBar barStyle="light-content" />
        <AuthProvider>
          <RootNavigator />
        </AuthProvider>
      </View>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  root: {flex: 1, backgroundColor: colors.background},
});
