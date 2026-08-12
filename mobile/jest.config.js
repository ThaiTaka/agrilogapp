/**
 * Jest configuration.
 *
 * Two things the React Native template does not set up for us:
 *
 * 1. `transformIgnorePatterns` — node_modules is not transformed by default,
 *    but most of this app's dependencies ship untranspiled ESM. Each package
 *    listed below produced a literal "Cannot use import statement outside a
 *    module" until it was added.
 *
 * 2. Native modules — WatermelonDB's SQLite adapter, AsyncStorage and
 *    gesture-handler all reach for a native bridge that does not exist in
 *    Node. They are mocked in jest.setup.js.
 *
 * Tests that need real database behaviour do not belong here; the local
 * stock-restore logic (Issue #26) is tested against WatermelonDB's LokiJS
 * adapter in its own suite.
 */

const esmPackages = [
  '@react-native',
  'react-native',
  '@react-navigation',
  'react-native-gesture-handler',
  'react-native-screens',
  'react-native-safe-area-context',
  'react-native-svg',
  'react-native-chart-kit',
  'react-native-get-random-values',
  '@react-native-async-storage',
  '@nozbe',
  // uuid v14 ships ESM only — the ID generator behind rule R1 sits on this.
  'uuid',
].join('|');

module.exports = {
  // React Native 0.87 ships the preset as its own package; the bare
  // 'react-native' preset name no longer resolves.
  preset: '@react-native/jest-preset',
  setupFiles: ['<rootDir>/jest.setup.js'],
  transformIgnorePatterns: [`node_modules/(?!(?:${esmPackages})/)`],
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json', 'node'],
  collectCoverageFrom: [
    'src/**/*.{ts,tsx}',
    '!src/**/__tests__/**',
    '!src/**/*.d.ts',
  ],
};
