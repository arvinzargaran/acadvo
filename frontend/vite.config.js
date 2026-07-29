import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      injectRegister: 'auto',
      includeAssets: ['favicon.svg', 'apple-touch-icon.png'],
      manifest: {
        name: 'Acadvo — AI Academic Advisor',
        short_name: 'Acadvo',
        description:
          'Plan your degree, track your GPA, and manage co-op applications in one place. An AI academic advisor built for Canadian university students.',
        display: 'standalone',
        start_url: '/',
        scope: '/',
        theme_color: '#F1EADB',
        background_color: '#F1EADB',
        icons: [
          {
            src: 'pwa-192x192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'any',
          },
          {
            src: 'pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any',
          },
          {
            src: 'maskable-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,ico,woff,woff2}'],
        // Serve index.html for client-side routes, but never shadow the
        // backend API — these paths must always hit the network.
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api\//],
        // No runtime caching for API/auth'd data: stale responses in an
        // authenticated app are a correctness bug, not an offline win.
        cleanupOutdatedCaches: true,
      },
    }),
  ],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.js'],
    // PWA/service-worker plumbing isn't relevant to unit tests.
    css: false,
  },
});
