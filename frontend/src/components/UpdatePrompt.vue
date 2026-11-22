<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useDialog } from 'naive-ui'
import { api } from '../api'

const dialog = useDialog()
let baseline = ''
let prompted = ''
let checking = false
let timer: number | undefined

async function checkVersion() {
  if (checking) return
  checking = true
  try {
    const { build_id: buildId } = await api.version()
    if (!buildId) return
    if (!baseline) {
      baseline = buildId
      return
    }
    if (buildId === baseline || buildId === prompted) return

    prompted = buildId
    dialog.info({
      title: '发现新版本',
      content: '刷新页面后即可使用最新版本。正在填写的内容请先保存。',
      positiveText: '刷新页面',
      negativeText: '稍后',
      onPositiveClick: () => {
        window.location.reload()
      },
    })
  } catch {
    // 版本检查失败不影响使用；下次回到页面时再试。
  } finally {
    checking = false
  }
}

function handleVisible() {
  if (document.visibilityState === 'visible') void checkVersion()
}

onMounted(() => {
  if (!import.meta.env.PROD) return
  void checkVersion()
  document.addEventListener('visibilitychange', handleVisible)
  window.addEventListener('focus', handleVisible)
  timer = window.setInterval(handleVisible, 5 * 60 * 1000)
})

onUnmounted(() => {
  document.removeEventListener('visibilitychange', handleVisible)
  window.removeEventListener('focus', handleVisible)
  if (timer !== undefined) window.clearInterval(timer)
})
</script>

<template>
  <span aria-hidden="true" style="display: none" />
</template>
