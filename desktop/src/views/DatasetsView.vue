<script setup lang="ts">
import EmptyState from '../components/EmptyState.vue'
import { t } from '../locales'
</script>

<template>
  <!-- 数据集管理页面入口与当前数据集状态。 -->
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">{{ t('datasets.title') }}</h1>
    </div>
    <div class="panel">
      <EmptyState icon="▦" :title="t('datasets.title')" :description="t('datasets.empty')" />
    </div>
  </div>
</template>
