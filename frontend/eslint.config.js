import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    rules: {
      'no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]' }],
    },
  },
  {
    /**
     * Las pruebas de interfaz corren en Node, no en el navegador: necesitan
     * `process` y no tienen nada que ver con React.
     *
     * La regla de los hooks hay que apagarla aqui porque los fixtures de
     * Playwright reciben una funcion llamada `use`, y el plugin la confunde
     * con el hook `use` de React 19.
     */
    files: ['playwright.config.js', 'pruebas/**/*.{js,mjs}'],
    languageOptions: {
      globals: { ...globals.node },
    },
    rules: {
      'react-hooks/rules-of-hooks': 'off',
      'react-refresh/only-export-components': 'off',
    },
  },
])
