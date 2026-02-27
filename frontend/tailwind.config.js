import defaultTheme from 'tailwindcss/defaultTheme'

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', ...defaultTheme.fontFamily.sans],
      },
      colors: {
        surface: {
          50:  '#e0f0f5',
          100: '#b8dce5',
          800: '#053d52',
          900: '#034159',
          950: '#032F40',
        },
        accent: {
          300: '#a3d4d4',
          400: '#7EBFBF',
          500: '#5fa8a8',
          600: '#4a9090',
        },
        glow: {
          gold:   '#BF9F3F',
          copper: '#8C5B3F',
          cyan:   '#7EBFBF',
          purple: '#BF9F3F',
        },
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%':      { transform: 'translateY(-12px)' },
        },
        fadeIn: {
          '0%':   { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideUp: {
          '0%':   { opacity: '0', transform: 'translateY(24px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseGlow: {
          '0%, 100%': { boxShadow: '0 0 8px rgba(126, 191, 191, 0.4)' },
          '50%':      { boxShadow: '0 0 20px rgba(126, 191, 191, 0.7)' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        gradientShift: {
          '0%':   { backgroundPosition: '0% 50%' },
          '50%':  { backgroundPosition: '100% 50%' },
          '100%': { backgroundPosition: '0% 50%' },
        },
      },
      animation: {
        float:         'float 8s ease-in-out infinite',
        fadeIn:         'fadeIn 0.5s ease-out',
        slideUp:        'slideUp 0.6s ease-out',
        pulseGlow:      'pulseGlow 2s ease-in-out infinite',
        shimmer:        'shimmer 2s infinite',
        gradientShift:  'gradientShift 15s ease infinite',
      },
      backdropBlur: {
        xs:   '2px',
        '2xl': '40px',
        '3xl': '64px',
      },
      boxShadow: {
        'glow-sm':     '0 0 10px rgba(126, 191, 191, 0.3)',
        'glow':        '0 0 20px rgba(126, 191, 191, 0.3), 0 0 60px rgba(126, 191, 191, 0.1)',
        'glow-lg':     '0 0 30px rgba(126, 191, 191, 0.5), 0 0 80px rgba(126, 191, 191, 0.2)',
        'glow-cyan':   '0 0 20px rgba(126, 191, 191, 0.3), 0 0 60px rgba(126, 191, 191, 0.1)',
        'glow-gold':   '0 0 20px rgba(191, 159, 63, 0.3), 0 0 60px rgba(191, 159, 63, 0.1)',
        'glow-copper': '0 0 20px rgba(140, 91, 63, 0.3), 0 0 60px rgba(140, 91, 63, 0.1)',
      },
    },
  },
  plugins: [],
}
