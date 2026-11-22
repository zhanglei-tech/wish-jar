<script setup lang="ts">
withDefaults(
  defineProps<{
    emoji?: string
    title: string
    text?: string
  }>(),
  {
    emoji: '🫙',
    text: '',
  },
)
</script>

<template>
  <div class="empty-state">
    <span class="emoji">{{ emoji }}</span>
    <strong>{{ title }}</strong>
    <p v-if="text">{{ text }}</p>
  </div>
</template>
