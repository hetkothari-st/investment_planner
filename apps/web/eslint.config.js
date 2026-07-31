import js from '@eslint/js'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist'] },
  {
    files: ['src/**/*.{ts,tsx}'],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: { ecmaVersion: 2022 },
  },
  {
    // The design fence: only src/design/ may define a colour.
    files: ['src/**/*.{ts,tsx}'],
    ignores: ['src/design/**'],
    rules: {
      'no-restricted-syntax': [
        'error',
        {
          selector: 'Literal[value=/#[0-9a-fA-F]{3,8}\\b/]',
          message: 'Hex colours are only defined in src/design/. Use a token.',
        },
        {
          selector: 'TemplateElement[value.raw=/#[0-9a-fA-F]{3,8}\\b/]',
          message: 'Hex colours are only defined in src/design/. Use a token.',
        },
      ],
    },
  },
)
