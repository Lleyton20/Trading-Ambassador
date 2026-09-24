import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon-32x32.png', 'apple-touch-icon.png'],
      // Service worker is normally build-only; enabled in dev too so
      // `npm run dev` is enough to test installability without a
      // separate build+preview step. `npm run build && npm run preview`
      // is still the truer check of production behavior.
      devOptions: { enabled: true, type: 'module' },
      // Precaches only the build's own JS/CSS/HTML/icons - never /api/*.
      // This is a live dashboard; caching market data in the service
      // worker would show stale prices instead of "offline", so no
      // runtimeCaching rules are added for API routes on purpose.
      manifest: {
        name: 'Trading Ambassador',
        short_name: 'Trading Ambassador',
        description:
          'Market intelligence and trading analysis for Forex - SMC structure, confluence, news, and price-zone alerts.',
        theme_color: '#0b0f14',
        background_color: '#0b0f14',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: 'pwa-64x64.png', sizes: '64x64', type: 'image/png' },
          { src: 'pwa-192x192.png', sizes: '192x192', type: 'image/png' },
          { src: 'pwa-512x512.png', sizes: '512x512', type: 'image/png' },
          {
            src: 'maskable-icon-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
    }),
  ],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
