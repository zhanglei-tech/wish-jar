import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './styles.css'

createApp(App).use(createPinia()).use(router).mount('#app')

// PWA 仅提供安装能力，不缓存资源；开发环境不注册。
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/sw.js', { updateViaCache: 'none' })
      .catch(() => {
        // 注册失败不影响正常网页使用；应用本就不承诺离线可用。
      })
  })
}
