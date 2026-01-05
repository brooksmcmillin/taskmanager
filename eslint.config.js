import security from 'eslint-plugin-security';
import sdl from '@microsoft/eslint-plugin-sdl';

export default [
  {
    ignores: ['node_modules/**', 'dist/**', '.astro/**'],
  },
  {
    files: ['**/*.js'],
    plugins: {
      security,
      '@microsoft/sdl': sdl,
    },
    rules: {
      // Security plugin rules
      'security/detect-object-injection': 'off',
      'security/detect-non-literal-fs-filename': 'warn',
      'security/detect-non-literal-regexp': 'warn',
      'security/detect-unsafe-regex': 'error',
      'security/detect-buffer-noassert': 'error',
      'security/detect-child-process': 'warn',
      'security/detect-disable-mustache-escape': 'error',
      'security/detect-eval-with-expression': 'error',
      'security/detect-no-csrf-before-method-override': 'error',
      'security/detect-possible-timing-attacks': 'warn',
      'security/detect-pseudoRandomBytes': 'error',
      'security/detect-new-buffer': 'error',
      'security/detect-non-literal-require': 'warn',

      // SDL plugin rules
      '@microsoft/sdl/no-inner-html': 'error',
      '@microsoft/sdl/no-document-write': 'error',
    },
  },
];
