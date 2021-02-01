module.exports = {
  // Automatically clear mock calls and instances between every test
  clearMocks: true,


  // The directory where Jest should output its coverage files
  coverageDirectory: "coverage",

  // An array of regexp pattern strings used to skip coverage collection
  coveragePathIgnorePatterns: [
    "/node_modules/"
  ],

  // A set of global variables that need to be available in all test environments
  globals: {
    moj: {
      Modules: {}
    }
  },

  // A list of paths to directories that Jest should use to search for files in
  roots: ["/src"],

  // A list of paths to modules that run some code to configure or set up the testing framework before each test
  setupFilesAfterEnv: [
    "/src/jest.setup.js"
  ],

  // An array of regexp pattern strings that are matched against all source file paths, matched files will skip transformation
  transformIgnorePatterns: [
    "/node_modules/",
    "\\.test\\.js"
  ],

};
