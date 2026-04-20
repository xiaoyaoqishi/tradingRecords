import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/ledger/',
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          if (id.includes('recharts')) return 'charts'
          if (id.includes('node_modules/antd/es/')) {
            const seg = id.split('node_modules/antd/es/')[1]?.split('/')[0]
            if (seg) return `antd-${seg}`
          }
          if (id.includes('@ant-design/icons')) return 'antd-icons'
          if (id.includes('/react/') || id.includes('/react-dom/') || id.includes('react-router-dom')) return 'react-vendor'
        },
      },
    },
  },
  server: {
    port: 5176,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
