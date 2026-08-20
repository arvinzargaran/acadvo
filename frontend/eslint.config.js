import js from '@eslint/js';
import globals from 'globals';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import jsxA11y from 'eslint-plugin-jsx-a11y';

/**
 * Lint config, added after an accessibility audit found that every form field in
 * the app was unlabelled (the `<label>` sat beside the input with no `htmlFor`)
 * and the university/program combobox was unreachable by keyboard. Both were
 * invisible to tests and to review; both are exactly what jsx-a11y catches.
 *
 * The rule set is deliberately narrow: correctness and accessibility, no style
 * opinions. A linter that reports 400 formatting nits gets switched off, and
 * then it catches nothing at all.
 */
export default [
  {
    ignores: ['dist/**', 'node_modules/**', 'dev-dist/**', 'public/**'],
  },
  js.configs.recommended,
  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: 'module',
      globals: { ...globals.browser, ...globals.es2021 },
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    settings: { react: { version: 'detect' } },
    plugins: {
      react,
      'react-hooks': reactHooks,
      'jsx-a11y': jsxA11y,
    },
    rules: {
      ...react.configs.flat.recommended.rules,
      ...jsxA11y.flatConfigs.recommended.rules,
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',

      // The app uses the automatic JSX runtime (Vite), so React need not be in
      // scope, and prop-types is not the validation story here.
      'react/react-in-jsx-scope': 'off',
      'react/prop-types': 'off',
      // Apostrophes in ordinary copy are fine and readable in source.
      'react/no-unescaped-entities': 'off',

      // An unused variable is usually a half-finished edit; an unused *argument*
      // often is not (callback signatures). Underscore opts out either way.
      'no-unused-vars': ['error', {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_',
        caughtErrors: 'none',
      }],
    },
  },
  {
    files: ['**/*.test.{js,jsx}', 'vitest.setup.js'],
    languageOptions: { globals: { ...globals.node, ...globals.vitest } },
  },
  {
    files: ['*.config.js', 'scripts/**/*.mjs', 'scripts/**/*.js'],
    languageOptions: { globals: { ...globals.node } },
  },
];
