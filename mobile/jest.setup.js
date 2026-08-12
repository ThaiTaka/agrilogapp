/* eslint-env jest */
/**
 * Native module stubs for the Node test environment.
 *
 * Everything mocked here talks to a native bridge that does not exist outside
 * a device. The stubs are deliberately thin: they exist so a component tree
 * can render, not so behaviour can be asserted through them. Any test that
 * needs real behaviour from one of these should use the real thing (e.g. the
 * LokiJS adapter for WatermelonDB) rather than making the mock smarter.
 */

require('react-native-gesture-handler/jestSetup');

// ─── AsyncStorage ───────────────────────────────────────────────────────────
// v3 API: getItem/setItem/removeItem plus getMany/setMany/removeMany.
jest.mock('@react-native-async-storage/async-storage', () => {
  const store = new Map();
  return {
    __esModule: true,
    default: {
      getItem: jest.fn(async key => (store.has(key) ? store.get(key) : null)),
      setItem: jest.fn(async (key, value) => {
        store.set(key, value);
      }),
      removeItem: jest.fn(async key => {
        store.delete(key);
      }),
      getMany: jest.fn(async keys =>
        Object.fromEntries(keys.map(k => [k, store.has(k) ? store.get(k) : null])),
      ),
      setMany: jest.fn(async entries => {
        for (const [k, v] of Object.entries(entries)) {
          store.set(k, v);
        }
      }),
      removeMany: jest.fn(async keys => {
        keys.forEach(k => store.delete(k));
      }),
      getAllKeys: jest.fn(async () => [...store.keys()]),
      clear: jest.fn(async () => {
        store.clear();
      }),
    },
  };
});

// ─── WatermelonDB SQLite adapter ────────────────────────────────────────────
// The JSI adapter binds to a native library. Schema-shape tests import
// src/db/schema directly and never touch this.
jest.mock('@nozbe/watermelondb/adapters/sqlite', () => {
  return {
    __esModule: true,
    default: jest.fn().mockImplementation(() => ({
      underlyingAdapter: {_dispatcher: {type: 'jsi'}},
    })),
  };
});

// ─── react-native-safe-area-context ─────────────────────────────────────────
// Without this the provider measures insets natively, finds nothing, and
// renders `children: null` — so every component test sees an empty tree and
// passes or fails for the wrong reason. The library ships this mock for
// exactly that case.
// The shipped mock puts every component on `default` rather than exporting
// them as named members, so it has to be unwrapped — passing it through
// as-is leaves SafeAreaProvider undefined and React fails with the unhelpful
// "Element type is invalid" instead.
jest.mock('react-native-safe-area-context', () => {
  const mock = require('react-native-safe-area-context/jest/mock');
  return mock.default ?? mock;
});

// ─── react-native-screens ───────────────────────────────────────────────────
jest.mock('react-native-screens', () => {
  const actual = jest.requireActual('react-native-screens');
  return {...actual, enableScreens: jest.fn()};
});

// NOTE: no NativeAnimatedHelper mock. The path many RN Jest guides still
// recommend (react-native/Libraries/Animated/NativeAnimatedHelper) does not
// exist in 0.87, and because the preset's moduleNameMapper claims the whole
// `react-native/*` namespace, `virtual: true` cannot rescue it — the mapper
// resolves first and fails. The 0.87 preset handles Animated itself.
