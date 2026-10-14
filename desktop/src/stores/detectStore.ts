/** Persist image-detect workspace across route changes. */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { BoxObject } from '../components/CanvasStage.vue'

export interface GalleryItem {
  path: string
  url: string
  thumb?: string
  name: string
  objects?: BoxObject[]
  status?: 'idle' | 'processing' | 'done' | 'empty'
}

export interface ModelItem {
  model_id: string
  name: string
  loaded: boolean
  class_list: Array<{ class_id: number; class_name: string; display_name: string }>
}

export const useDetectStore = defineStore('detect', () => {
  const mediaPath = ref('')
  const mediaKind = ref<'image' | 'folder' | 'unknown'>('unknown')
  const imageUrl = ref('')
  const objects = ref<BoxObject[]>([])
  const selectedId = ref<number | null>(null)
  const models = ref<ModelItem[]>([])
  const selectedModels = ref<string[]>([])
  const classFilter = ref<Record<string, string[]>>({})
  const conf = ref(0.45)
  const labelTemplate = ref('{id}:{class}')
  const maxSide = ref(1280)
  const lastImageTaskId = ref('')
  const gallery = ref<GalleryItem[]>([])
  const currentGalleryIndex = ref(0)
  const selectedGalleryPaths = ref<string[]>([])
  const sessionMode = ref<'temp' | 'project'>('temp')
  const infoMsg = ref('')
  const errorMsg = ref('')

  function resetMedia(): void {
    mediaPath.value = ''
    mediaKind.value = 'unknown'
    imageUrl.value = ''
    objects.value = []
    selectedId.value = null
    gallery.value = []
    currentGalleryIndex.value = 0
    selectedGalleryPaths.value = []
    lastImageTaskId.value = ''
  }

  return {
    mediaPath,
    mediaKind,
    imageUrl,
    objects,
    selectedId,
    models,
    selectedModels,
    classFilter,
    conf,
    labelTemplate,
    maxSide,
    lastImageTaskId,
    gallery,
    currentGalleryIndex,
    selectedGalleryPaths,
    sessionMode,
    infoMsg,
    errorMsg,
    resetMedia
  }
})
