/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './apps/**/templates/**/*.html',
    './apps/**/*.py',
  ],
  theme: {
    extend: {
      colors: {
        accent: '#2e7cf6',
        'accent-dark': '#1e5bd1',
        teal: '#1fc8c5',
        ink: '#0e1a2b',
        'ink-2': '#3a4a60',
        'ink-3': '#7a8a9f',
        surface: '#f4f8fc',
      },
      fontFamily: { sans: ['Onest', 'sans-serif'] },
      borderRadius: { card: '18px' },
    },
  },
};
