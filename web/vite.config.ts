import path from 'path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const apiOrigin = process.env.NEXUS_API_ORIGIN ?? 'http://localhost:8000';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/v1': {
        target: apiOrigin,
        changeOrigin: true,
      },
      '/health': {
        target: apiOrigin,
        changeOrigin: true,
      },
    },
  },
});
