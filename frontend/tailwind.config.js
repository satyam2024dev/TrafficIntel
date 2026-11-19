/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        traffic: {
          canvas: '#EEF2F6',
          canvasBorder: '#CBD5E1',
          bg: '#E2E8F0',
          card: '#FFFFFF',
          surface: '#F8FAFC',
          border: '#E2E8F0',
          borderStrong: '#CBD5E1',
          text: '#0F172A',
          muted: '#64748B',
          accent: '#00A8C6',
          accentHover: '#0090AA',
          accentTeal: '#0891B2',
          success: '#059669',
          warning: '#F59E0B',
          danger: '#EF4444',
          midnight: '#111C2D',
          midnightBorder: '#26354D',
          midnightInput: '#09111E',
          rail: '#FFFFFF',
          railBorder: '#E2E8F0',
        }
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Courier New', 'monospace']
      },
      animation: {
        'pulse-glow': 'pulseGlow 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'radar-sweep': 'radarSweep 3s linear infinite',
      },
      keyframes: {
        pulseGlow: {
          '0%, 100%': { opacity: '1', boxShadow: '0 0 12px rgba(37, 99, 235, 0.4)' },
          '50%': { opacity: '.6', boxShadow: '0 0 4px rgba(37, 99, 235, 0.15)' },
        },
        radarSweep: {
          '0%': { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(360deg)' },
        }
      }
    },
  },
  plugins: [],
}
