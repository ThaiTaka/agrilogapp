module.exports = {
  presets: ['module:@react-native/babel-preset'],
  plugins: [
    // WatermelonDB models are declared with legacy (stage-1) decorators:
    //   @text('name') name!: string
    //
    // Pinned to the v7 plugin because @babel/plugin-proposal-decorators@8
    // peer-depends on @babel/core@^8, while React Native 0.87 ships core v7.
    // `legacy: true` is required — the modern proposal has different
    // semantics and WatermelonDB's decorators do not work under it.
    ['@babel/plugin-proposal-decorators', {legacy: true}],

    // Must come AFTER the decorators plugin, and must be loose.
    //
    // In spec mode, class fields are emitted with Object.defineProperty, and
    // Babel's TypeScript plugin then rejects a definite-assignment field
    // (`name!: string`) that carries a decorator with:
    //   "Definitely assigned fields cannot be initialized here"
    // Loose mode emits plain assignment, which is also what WatermelonDB's
    // decorators expect — they install getters/setters on the prototype and
    // a defineProperty on the instance would shadow them.
    ['@babel/plugin-transform-class-properties', {loose: true}],
    ['@babel/plugin-transform-private-methods', {loose: true}],
    ['@babel/plugin-transform-private-property-in-object', {loose: true}],
  ],
};
