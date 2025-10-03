/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        'tg-bg': 'var(--tg-theme-bg-color)',
        'tg-text': 'var(--tg-theme-text-color)',
        'tg-hint': 'var(--tg-theme-hint-color)',
        'tg-link': 'var(--tg-theme-link-color)',
        'tg-button': 'var(--tg-theme-button-color)',
        'tg-button-text': 'var(--tg-theme-button-text-color)',
      },
      fontSize: {
        'xs': ['12px', '16px'],
        'sm': ['14px', '20px'],
        'base': ['16px', '24px'],
        'lg': ['18px', '28px'],
        'xl': ['20px', '28px'],
        '2xl': ['24px', '32px'],
      },
      minHeight: {
        'touch': '44px',
      },
      minWidth: {
        'touch': '44px',
      }
    },
  },
  plugins: [],
}