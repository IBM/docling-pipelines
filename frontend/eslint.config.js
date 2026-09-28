import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from '@typescript-eslint/eslint-plugin'
import tsparser from '@typescript-eslint/parser'
import react from 'eslint-plugin-react'
import formatjs from 'eslint-plugin-formatjs'
import boundaries from 'eslint-plugin-boundaries'

export default [
  {
    ignores: ['dist', 'node_modules', 'build', '*.config.js', '*.config.ts']
  },
  // BFF server — Node environment, separate tsconfig
  {
    files: ['server/**/*.ts'],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.node,
      parser: tsparser,
      parserOptions: {
        ecmaVersion: 'latest',
        sourceType: 'module',
        project: './tsconfig.server.json',
      },
    },
    plugins: {
      '@typescript-eslint': tseslint,
    },
    rules: {
      ...js.configs.recommended.rules,
      ...tseslint.configs.recommended.rules,
      'no-console': 'error',
      'no-debugger': 'error',
      'no-var': 'error',
      'prefer-const': 'error',
      '@typescript-eslint/no-unused-vars': ['error', {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_',
        caughtErrorsIgnorePattern: '^_',
      }],
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/consistent-type-imports': ['error', {
        prefer: 'type-imports',
        fixStyle: 'inline-type-imports',
      }],
    },
  },
  // Frontend — browser environment
  {
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      parser: tsparser,
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
        project: './tsconfig.json',
      },
    },
    settings: {
      react: {
        version: '18.3',
      },
      'boundaries/include': ['src/**/*'],
      'boundaries/elements': [
        {
          type: 'pages',
          pattern: 'src/pages/**/*',
          partialMatch: false,
        },
        {
          type: 'components-common',
          pattern: 'src/components/common/**/*',
          partialMatch: false,
        },
        {
          type: 'components-domain',
          pattern: 'src/components/!(common)/**/*',
          partialMatch: false,
        },
      ],
    },
    plugins: {
      react,
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
      '@typescript-eslint': tseslint,
      formatjs,
      boundaries,
    },
    rules: {
      ...js.configs.recommended.rules,
      ...react.configs.recommended.rules,
      ...react.configs['jsx-runtime'].rules,
      ...reactHooks.configs.recommended.rules,
      ...tseslint.configs.recommended.rules,

      // React
      'react/react-in-jsx-scope': 'off',
      'react/prop-types': 'off',
      'react/jsx-first-prop-new-line': ['error', 'multiline'],
      'react/jsx-props-no-spreading': 'warn',
      'react/jsx-no-useless-fragment': ['error', { allowExpressions: true }],
      'react/no-unstable-nested-components': ['error', { allowAsProps: true }],
      'react/jsx-no-constructed-context-values': 'error',
      'react/no-array-index-key': 'warn',
      'react/jsx-key': 'error',
      'react/no-children-prop': 'error',
      'react/no-danger': 'warn',
      'react/no-deprecated': 'error',
      'react/self-closing-comp': 'error',
      'react/jsx-boolean-value': ['error', 'never'],
      'react/jsx-curly-brace-presence': ['error', { props: 'never', children: 'never' }],
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],

      // TypeScript - Type Safety
      '@typescript-eslint/no-unused-vars': ['error', {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_',
        caughtErrorsIgnorePattern: '^_',
      }],
      '@typescript-eslint/no-unsafe-call': 'error',
      '@typescript-eslint/no-unsafe-return': 'error',
      '@typescript-eslint/await-thenable': 'error',
      '@typescript-eslint/no-floating-promises': 'error',
      '@typescript-eslint/no-misused-promises': 'error',
      '@typescript-eslint/require-await': 'error',
      '@typescript-eslint/explicit-function-return-type': ['warn', {
        allowExpressions: true,
        allowTypedFunctionExpressions: true,
        allowHigherOrderFunctions: true,
        allowDirectConstAssertionInArrowFunctions: true,
      }],
      '@typescript-eslint/explicit-module-boundary-types': 'warn',
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-unsafe-assignment': 'warn',
      '@typescript-eslint/no-unsafe-member-access': 'warn',
      '@typescript-eslint/no-unsafe-argument': 'warn',

      // TypeScript - Code Quality
      '@typescript-eslint/array-type': ['error', { default: 'array-simple' }],
      '@typescript-eslint/consistent-type-imports': ['error', {
        prefer: 'type-imports',
        fixStyle: 'inline-type-imports',
      }],
      '@typescript-eslint/consistent-type-exports': 'error',
      '@typescript-eslint/no-confusing-void-expression': ['error', { ignoreVoidOperator: true }],
      '@typescript-eslint/no-duplicate-enum-values': 'error',
      '@typescript-eslint/no-duplicate-type-constituents': 'error',
      '@typescript-eslint/no-unnecessary-type-assertion': 'error',
      '@typescript-eslint/prefer-nullish-coalescing': 'error',
      '@typescript-eslint/prefer-optional-chain': 'error',

      // React Hooks
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',

      // Code Quality - Errors
      'no-console': 'error',
      'no-debugger': 'error',
      'no-alert': 'error',
      'no-var': 'error',
      'prefer-const': 'error',
      'eqeqeq': ['error', 'always'],
      'no-eval': 'error',
      'no-implied-eval': 'error',
      'no-new-func': 'error',
      'no-param-reassign': ['error', {
        props: true,
        ignorePropertyModificationsFor: ['state', 'draft', 'acc'],
      }],
      'no-return-await': 'error',
      'no-throw-literal': 'error',
      // Disabled in favour of @typescript-eslint/no-unused-expressions to avoid conflicts
      'no-unused-expressions': 'off',
      '@typescript-eslint/no-unused-expressions': 'error',
      'no-useless-concat': 'error',
      'no-useless-return': 'error',
      'require-await': 'off',

      // Code Quality - Warnings
      'curly': ['warn', 'all'],
      'default-case-last': 'warn',
      'no-else-return': 'warn',
      'no-lonely-if': 'warn',
      'no-unneeded-ternary': 'warn',
      'prefer-arrow-callback': 'warn',
      'prefer-destructuring': ['warn', { array: false, object: true }],
      'prefer-template': 'warn',
      'yoda': 'warn',

      // Style
      'arrow-parens': ['error', 'always'],
      'arrow-body-style': ['error', 'as-needed'],
      'comma-dangle': ['error', {
        arrays: 'always-multiline',
        objects: 'always-multiline',
        imports: 'always-multiline',
        exports: 'always-multiline',
        functions: 'never',
      }],
      'max-len': ['error', {
        code: 150,
        ignoreUrls: true,
        ignoreStrings: true,
        ignoreTemplateLiterals: true,
        ignoreRegExpLiterals: true,
      }],
      'no-multiple-empty-lines': ['error', { max: 1, maxEOF: 0 }],
      'no-tabs': 'error',
      'quotes': ['error', 'single', { avoidEscape: true }],
      'semi': ['error', 'always'],

      // Message descriptors
      'formatjs/enforce-default-message': 'error',
      'formatjs/enforce-placeholders': 'error',
      'formatjs/no-camel-case': 'warn',

      // Architecture Boundaries
      'boundaries/dependencies': ['error', {
        default: 'allow',
        policies: [
          {
            from: { element: { type: 'components-common' } },
            disallow: [
              { to: { element: { type: 'components-domain' } } },
              { to: { element: { type: 'pages' } } },
            ],
            message: 'src/components/common cannot import domain components from src/components or page-routing components from src/pages.',
          },
          {
            from: { element: { type: 'components-domain' } },
            disallow: [
              { to: { element: { type: 'pages' } } },
            ],
            message: 'src/components cannot import from page-routing components in src/pages.',
          },
        ],
      }],

      // Disabled
      '@typescript-eslint/ban-ts-comment': 'off',
      '@typescript-eslint/no-non-null-assertion': 'off',
      'react/display-name': 'off',
      'react/jsx-no-target-blank': 'off',
    },
  },
]
