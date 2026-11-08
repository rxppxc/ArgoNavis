import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
    rules: {
      // Un efecto es para sincronizar con algo de afuera (la red, el DOM, un temporizador):
      // un estado que sale de otro se calcula al renderizar, no en un efecto. Hoy no hay
      // ninguno (revisión del 2026-11-08); estas dos reglas lo mantienen así.
      'react-hooks/no-deriving-state-in-effects': 'error',
      'react-hooks/void-use-memo': 'error',
    },
  },
])
