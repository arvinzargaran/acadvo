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
        theme_color: '#1B62F0',
        background_color: '#FFFFFF',
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
  build: {
    rollupOptions: {
      output: {
        // Split heavy, rarely-changing vendors into their own long-cached chunks
        // instead of one ~900KB bundle. Improves first-paint and lets a redeploy
        // reuse cached vendor chunks (only the app chunk changes most releases).
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router'],
          animation: ['framer-motion', 'gsap', 'lenis'],
          markdown: ['react-markdown'],
        },
      },
    },
  },
  server: {
    // Honour PORT so more than one dev server can run side by side; falls back
    // to Vite's default when it isn't set.
    port: Number(process.env.PORT) || 5173,
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
