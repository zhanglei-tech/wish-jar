<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import {
  NConfigProvider,
  NDialogProvider,
  NMessageProvider,
  dateZhCN,
  zhCN,
} from 'naive-ui'
import { useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'
import { themeOverrides } from './theme'

const router = useRouter()
const auth = useAuthStore()

function handleUnauthorized() {
  auth.clearSession()
  if (router.currentRoute.value.name !== 'login' && router.currentRoute.value.name !== 'setup') {
    router.replace({ name: 'login' })
  }
}

onMounted(() => window.addEventListener('wishjar:unauthorized', handleUnauthorized))
onUnmounted(() => window.removeEventListener('wishjar:unauthorized', handleUnauthorized))
</script>

<template>
  <n-config-provider
    :theme-overrides="themeOverrides"
    :locale="zhCN"
    :date-locale="dateZhCN"
  >
    <n-message-provider>
      <n-dialog-provider>
        <router-view />
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>
