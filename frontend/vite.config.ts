import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig(() => ({
  plugins: [react()],
  // Always use /ui/ as base path for both dev and production
  base: '/ui/',
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@components': path.resolve(__dirname, './src/components'),
      '@pages': path.resolve(__dirname, './src/pages'),
      '@hooks': path.resolve(__dirname, './src/hooks'),
      '@contexts': path.resolve(__dirname, './src/contexts'),
      '@types': path.resolve(__dirname, './src/types'),
      '@config': path.resolve(__dirname, './src/config'),
      // Resolve @carbon-labs/utilities subpath export that esbuild can't follow
      '@carbon-labs/utilities/usePrefix': path.resolve(
        __dirname,
        './node_modules/@carbon-labs/utilities/es/usePrefix.js'
      ),
    },
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
  },
  server: {
    port: 3000,
    open: false,
    proxy: {
      // Proxy all /api/* requests to BFF server
      // This handles ALL API endpoints - no need to update for new endpoints
      '/api': {
        target: 'http://localhost:3001',
        changeOrigin: true
      }
    }
  }
}))
