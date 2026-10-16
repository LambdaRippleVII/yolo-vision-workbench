import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import './styles/tokens.css'
import './styles/shell.css'

// 创建 Vue 根实例，并挂载全局状态、路由和工作台外壳。
const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
