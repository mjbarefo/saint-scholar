module.exports = [
  {
    ignores: [
      "node_modules/**",
      "output/**",
      "vector_store/**",
      ".venv/**",
    ],
  },
  {
    files: ["src/saint_scholar/api/static/**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",
      globals: {
        URL: "readonly",
        confirm: "readonly",
        document: "readonly",
        fetch: "readonly",
        localStorage: "readonly",
        setInterval: "readonly",
        setTimeout: "readonly",
        window: "readonly",
      },
    },
    rules: {
      "no-undef": "error",
    },
  },
  {
    files: ["tests/**/*.js", "playwright.config.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "commonjs",
      globals: {
        __dirname: "readonly",
        document: "readonly",
        localStorage: "readonly",
        module: "readonly",
        process: "readonly",
        require: "readonly",
        window: "readonly",
      },
    },
    rules: {
      "no-undef": "error",
    },
  },
];
