<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'

const version = ref('')

const label = computed(() => {
  const raw = version.value.trim()
  if (!raw) return ''
  if (raw === 'dev') return '开发版'
  return /^\d/.test(raw) ? `v${raw}` : raw
})

onMounted(async () => {
  try {
    version.value = (await api.version()).version ?? ''
  } catch {
    // 版本号不是关键路径；读取失败时不显示。
  }
})
</script>

<template>
  <span v-if="label" class="app-version">版本 {{ label }}</span>
</template>
