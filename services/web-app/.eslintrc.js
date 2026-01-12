module.exports = {
  extends: [
    'eslint:recommended',
    'plugin:security/recommended',
    'plugin:@microsoft/sdl/required',
  ],
  plugins: ['security', '@microsoft/sdl'],
  rules: {
    // Security rules
    'security/detect-object-injection': 'warn',
    'security/detect-non-literal-regexp': 'warn',
    'security/detect-unsafe-regex': 'error',
    'security/detect-buffer-noassert': 'error',
    'security/detect-child-process': 'error',
    'security/detect-disable-mustache-escape': 'error',
    'security/detect-eval-with-expression': 'error',
    'security/detect-no-csrf-before-method-override': 'error',
    'security/detect-non-literal-fs-filename': 'warn',
    'security/detect-non-literal-require': 'warn',
    'security/detect-possible-timing-attacks': 'warn',
    'security/detect-pseudoRandomBytes': 'error',
    'security/detect-sql-injection': 'error',

    // Microsoft SDL rules
    '@microsoft/sdl/no-cookies': 'warn',
    '@microsoft/sdl/no-document-domain': 'error',
    '@microsoft/sdl/no-document-write': 'error',
    '@microsoft/sdl/no-html-method': 'error',
    '@microsoft/sdl/no-inner-html': 'warn',
    '@microsoft/sdl/no-insecure-url': 'error',
    '@microsoft/sdl/no-msapp-exec-unsafe': 'error',
    '@microsoft/sdl/no-postmessage-star-origin': 'error',
    '@microsoft/sdl/no-unsafe-alloc': 'error',
    '@microsoft/sdl/no-winjs-html-unsafe': 'error',
    '@microsoft/sdl/react-iframe-missing-sandbox': 'error',

    // Additional security patterns
    'no-eval': 'error',
    'no-implied-eval': 'error',
    'no-new-func': 'error',
    'no-return-await': 'error',
  },
  overrides: [
    {
      files: ['tests/**/*.js'],
      rules: {
        'security/detect-non-literal-fs-filename': 'off',
        'security/detect-object-injection': 'off',
      },
    },
  ],
};
