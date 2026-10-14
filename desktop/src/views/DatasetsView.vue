<script setup lang="ts">
import EmptyState from '../components/EmptyState.vue'
import { t } from '../locales'
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">{{ t('datasets.title') }}</h1>
    </div>
    <div class="panel">
      <EmptyState icon="▦" :title="t('datasets.title')" :description="t('datasets.empty')" />
    </div>
  </div>
</template>
