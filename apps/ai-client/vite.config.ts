import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/auth': {
        target: 'http://127.0.0.1:8005',
        changeOrigin: true,
      },
      '/collections': {
        target: 'http://127.0.0.1:8005',
        changeOrigin: true,
      },
      '/sessions': {
        target: 'http://127.0.0.1:8005',
        changeOrigin: true,
      },
    },
  },
})
