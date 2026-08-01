import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Vite 配置
// server.proxy：开发环境代理配置
// 前端跑在 5173 端口，后端 API 在 8001 端口
// 浏览器跨域限制：通过代理把 /api 请求转发到后端，避免 CORS 问题
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '127.0.0.1', // 显式绑定 IPv4，避免系统 IPv6 监听权限问题
    port: 8002, // 5173/5454 都在系统端口排除范围内无法绑定（动态变化），改用 8002
    strictPort: true, // 端口被占用时报错而不是换端口
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001', // 后端地址
        changeOrigin: true,
      },
      // AI 配图静态资源（后端本地存储目录，通过 /images 对外访问）
      '/images': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
    },
  },
})
