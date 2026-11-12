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
          bg: '#070b14',
          card: '#0f172a',
          surface: '#1e293b',
          border: '#334155',
          accent: '#06b6d4',
          success: '#10b981',
          warning: '#f59e0b',
          danger: '#ef4444',
          radar: '#38bdf8'
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
          '0%, 100%': { opacity: '1', boxShadow: '0 0 15px rgba(6, 182, 212, 0.6)' },
          '50%': { opacity: '.6', boxShadow: '0 0 5px rgba(6, 182, 212, 0.2)' },
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
