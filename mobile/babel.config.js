module.exports = {
  presets: ['module:@react-native/babel-preset'],
  plugins: [
    // WatermelonDB models are declared with legacy (stage-1) decorators:
    //   @text('name') name!: string
    // Pinned to the v7 plugin because @babel/plugin-proposal-decorators@8
    // peer-depends on @babel/core@^8, while React Native 0.87 ships core v7.
    // `legacy: true` is required — the modern proposal has different
    // semantics and WatermelonDB's decorators do not work under it.
    ['@babel/plugin-proposal-decorators', {legacy: true}],
  ],
};
