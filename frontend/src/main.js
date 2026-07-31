// 应用入口：创建 Vue 实例并挂载
// 这里集中注册：Element Plus 组件库、图标、路由、Pinia 状态管理
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn' // 中文语言包
import 'element-plus/dist/index.css' // Element Plus 样式
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'

const app = createApp(App)

// 注册所有 Element Plus 图标（图标以 <el-icon><User /></el-icon> 方式使用）
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia()) // 状态管理（用户登录态等）
app.use(router) // 路由
app.use(ElementPlus, { locale: zhCn }) // UI 组件库（中文界面）

app.mount('#app')
