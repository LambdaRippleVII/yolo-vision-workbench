<script setup lang="ts">
import { t } from '../locales'

const themeOptions = [
  { value: 'light', label: t('top.themeLight') },
  { value: 'dark', label: t('top.themeDark') }
]
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">{{ t('settings.title') }}</h1>
    </div>

    <div class="panel">
      <div class="panel-head">
        <h2 class="panel-title">{{ t('settings.sectionAppearance') }}</h2>
      </div>
      <div class="panel-body">
        <div class="field-row">
          <span class="field-label">{{ t('settings.theme') }}</span>
          <span class="field-value">
            <select>
              <option v-for="opt in themeOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </span>
        </div>
        <div class="field-row">
          <span class="field-label">{{ t('settings.language') }}</span>
          <span class="field-value">简体中文</span>
        </div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-head">
        <h2 class="panel-title">{{ t('settings.sectionBackend') }}</h2>
      </div>
      <div class="panel-body">
        <div class="field-row">
          <span class="field-label">{{ t('settings.port') }}</span>
          <span class="field-value num">8765</span>
        </div>
        <div class="field-row">
          <span class="field-label">{{ t('settings.logLevel') }}</span>
          <span class="field-value">INFO</span>
        </div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-head">
        <h2 class="panel-title">{{ t('settings.sectionAbout') }}</h2>
      </div>
      <div class="panel-body muted-text">{{ t('settings.aboutText') }}</div>
    </div>
  </div>
</template>

<style scoped>
select {
  height: 32px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-panel);
  color: var(--text-primary);
  padding: 0 8px;
  font-size: var(--text-md);
}
.muted-text {
  color: var(--text-muted);
}
</style>
