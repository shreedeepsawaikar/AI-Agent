import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/research': 'http://127.0.0.1:5000',
      '/research-clear-history': 'http://127.0.0.1:5000',
      '/product-search': 'http://127.0.0.1:5000',
      '/multi-step': 'http://127.0.0.1:5000',
      '/multi-step-approve': 'http://127.0.0.1:5000',
      '/rag-files': 'http://127.0.0.1:5000',
      '/rag-upload': 'http://127.0.0.1:5000',
      '/rag-delete': 'http://127.0.0.1:5000',
      '/rag-reindex': 'http://127.0.0.1:5000',
      '/rag-query': 'http://127.0.0.1:5000',
      '/rag-clear-history': 'http://127.0.0.1:5000',
    }
  }
})
