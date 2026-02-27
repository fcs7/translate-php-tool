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
          50:  '#f8fafc',
          100: '#f1f5f9',
          800: '#1e1b4b',
          900: '#0f0d2e',
          950: '#080620',
        },
        accent: {
          400: '#818cf8',
          500: '#6366f1',
          600: '#4f46e5',
        },
        glow: {
          blue:   '#3b82f6',
          purple: '#8b5cf6',
          cyan:   '#06b6d4',
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
          '0%, 100%': { boxShadow: '0 0 8px rgba(99, 102, 241, 0.4)' },
          '50%':      { boxShadow: '0 0 20px rgba(99, 102, 241, 0.7)' },
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
        'glow-sm':     '0 0 10px rgba(99, 102, 241, 0.3)',
        'glow':        '0 0 20px rgba(99, 102, 241, 0.3), 0 0 60px rgba(99, 102, 241, 0.1)',
        'glow-lg':     '0 0 30px rgba(99, 102, 241, 0.5), 0 0 80px rgba(99, 102, 241, 0.2)',
        'glow-cyan':   '0 0 20px rgba(6, 182, 212, 0.3), 0 0 60px rgba(6, 182, 212, 0.1)',
        'glow-purple': '0 0 20px rgba(139, 92, 246, 0.3), 0 0 60px rgba(139, 92, 246, 0.1)',
        'glow-blue':   '0 0 20px rgba(59, 130, 246, 0.3), 0 0 60px rgba(59, 130, 246, 0.1)',
      },
    },
  },
  plugins: [],
}
