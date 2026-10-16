import { createRouter, createWebHashHistory } from 'vue-router'
import ImageDetectView from '../views/ImageDetectView.vue'
import VideoEditorView from '../views/VideoEditorView.vue'
import CameraView from '../views/CameraView.vue'
import CameraPopoutView from '../views/CameraPopoutView.vue'
import ProjectsView from '../views/ProjectsView.vue'
import ModelsView from '../views/ModelsView.vue'
import DatasetsView from '../views/DatasetsView.vue'
import TasksView from '../views/TasksView.vue'
import DevicesView from '../views/DevicesView.vue'
import SettingsView from '../views/SettingsView.vue'

/** 在浏览器支持时用原生视图过渡执行路由切换回调。 */
export function withViewTransition(fn: () => void | Promise<unknown>): void {
  const doc = document as unknown as {
    startViewTransition?: (cb: () => void | Promise<void>) => unknown
  }
  if (typeof doc.startViewTransition === 'function') {
    void doc.startViewTransition(async () => {
      await fn()
    })
  } else {
    void fn()
  }
}

// 应用主路由表；图片检测和模型管理页保留实例以维持工作区状态。
export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/image' },
    {
      path: '/image',
      name: 'image',
      component: ImageDetectView,
      meta: { keepAlive: true }
    },
    { path: '/video-editor', name: 'video-editor', component: VideoEditorView },
    { path: '/camera', name: 'camera', component: CameraView },
    { path: '/camera-popout', name: 'camera-popout', component: CameraPopoutView },
    { path: '/projects', name: 'projects', component: ProjectsView },
    {
      path: '/models',
      name: 'models',
      component: ModelsView,
      meta: { keepAlive: true }
    },
    { path: '/datasets', name: 'datasets', component: DatasetsView },
    { path: '/tasks', name: 'tasks', component: TasksView },
    { path: '/devices', name: 'devices', component: DevicesView },
    { path: '/settings', name: 'settings', component: SettingsView },
    { path: '/workbench', redirect: '/image' },
    { path: '/:pathMatch(.*)*', redirect: '/image' }
  ]
})

router.afterEach(() => {
  const el = document.querySelector('.shell-main') as HTMLElement | null
  if (el) el.style.setProperty('view-transition-name', 'shell-main')
})
