const { getDefaultConfig, mergeConfig } = require('@react-native/metro-config');

/**
 * Metro configuration
 * https://reactnative.dev/docs/metro
 *
 * @type {import('@react-native/metro-config').MetroConfig}
 */
const config = {
  resolver: {
    // Excludes native build output from Metro's file watcher, not just from
    // module resolution. Without this, Metro watches the whole project tree
    // including android/app/.cxx -- and Gradle's CMake step creates and
    // deletes CMakeTmp probe directories there within milliseconds. Watchman
    // handles that fine; the Node fs.watch fallback Metro uses when Watchman
    // is not installed does not -- it throws ENOENT on a directory that
    // vanished between the watch call and the OS registering it, and that
    // exception is unhandled: it kills the whole Metro process rather than
    // just failing one file, which then makes the app report the unrelated-
    // looking "Unable to load script."
    //
    // `metro-config/src/defaults/exclusionList` (the usual way to build this)
    // is a deep import current metro-config's package.json `exports` map
    // blocks, so this is a plain RegExp array instead -- `blockList` accepts
    // one directly, and Metro's own config merge concatenates it with the
    // framework defaults rather than replacing them.
    blockList: [
      /android[/\\](app[/\\])?build[/\\].*/,
      /android[/\\]app[/\\]\.cxx[/\\].*/,
      /android[/\\]\.gradle[/\\].*/,
      /ios[/\\]build[/\\].*/,
      /ios[/\\]Pods[/\\].*/,
    ],
  },
};

module.exports = mergeConfig(getDefaultConfig(__dirname), config);
