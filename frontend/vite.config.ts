import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/

export default defineConfig({
  // during development we want assets served from root; in production
  // build the files with relative paths so Flask can serve them from
  // whatever location (we use './' which makes index.html reference
  // assets relatively).
  base: './',
  build: {
    outDir: '../static',
    emptyOutDir: true,
  },
  plugins: [
    vue(),
    vueDevTools(),
  ],
  
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
})
