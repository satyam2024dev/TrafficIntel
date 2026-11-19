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
          bg: '#090A0F',
          card: '#11131A',
          surface: '#171A24',
          border: '#222634',
          borderStrong: '#2B3040',
          accent: '#2563EB',
          accentHover: '#1D4ED8',
          accentFocus: '#3B82F6',
          success: '#10B981',
          warning: '#F59E0B',
          danger: '#EF4444',
          radar: '#3B82F6',
          rail: '#0D0F16',
          railBorder: '#1F2330',
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
