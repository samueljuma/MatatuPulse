/** @type {import('tailwindcss').Config} */
// Palette from designs/Design System.png. Red (alert) is reserved for verified alerts.
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: '#0F766E', tint: '#CCFBF1', dark: '#115E59' },
        ink: '#1F2937',
        muted: '#6B7280',
        background: '#F9FAFB',
        surface: '#FFFFFF',
        border: '#E5E7EB',
        alert: { DEFAULT: '#DC2626', tint: '#FEE2E2' },
        'fare-up': { DEFAULT: '#D97706', tint: '#FEF3C7', text: '#92400E' },
        'fare-normal': { DEFAULT: '#16A34A', tint: '#DCFCE7', text: '#15803D' },
        pending: { DEFAULT: '#9CA3AF', tint: '#F3F4F6', text: '#4B5563' },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        '28': ['28px', { lineHeight: '36px', fontWeight: '700' }],
      },
      borderRadius: {
        xl: '12px',
      },
    },
  },
  plugins: [],
}
