<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  points: number
  level: number
  progress: number
}>()

const fillHeight = computed(() => {
  const ratio = Math.min(100, Math.max(0, props.progress)) / 100
  return 8 + ratio * 144
})

const fillY = computed(() => 232 - fillHeight.value)
</script>

<template>
  <div class="jar-wrap">
    <svg class="jar-svg" viewBox="0 0 220 260" role="img" aria-label="心愿罐">
      <defs>
        <linearGradient id="jarFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#f7c65e" />
          <stop offset="55%" stop-color="#f2b544" />
          <stop offset="100%" stop-color="#e86a4a" />
        </linearGradient>
        <clipPath id="jarClip">
          <path
            d="M62 82 C62 70 72 65 78 57 L78 50 H142 L142 57 C148 65 158 70 158 82 L166 200 C168 222 152 236 132 236 H88 C68 236 52 222 54 200 Z"
          />
        </clipPath>
      </defs>

      <rect x="52" y="24" width="116" height="24" rx="12" class="jar-lid" />
      <rect x="70" y="45" width="80" height="9" rx="4.5" fill="#f2b544" opacity="0.9" />

      <g clip-path="url(#jarClip)">
        <rect
          class="jar-liquid"
          x="0"
          :y="fillY"
          width="220"
          :height="260 - fillY"
        />
        <circle class="jar-bubble" cx="92" cy="188" r="4" />
        <circle class="jar-bubble" cx="126" cy="166" r="3" />
        <circle class="jar-bubble" cx="112" cy="204" r="2.4" />
      </g>

      <path
        class="jar-glass"
        d="M62 82 C62 70 72 65 78 57 L78 50 H142 L142 57 C148 65 158 70 158 82 L166 200 C168 222 152 236 132 236 H88 C68 236 52 222 54 200 Z"
      />
      <path
        class="jar-highlight"
        d="M73 94 C68 126 68 166 73 200"
        fill="none"
        stroke="rgba(255,255,255,0.72)"
        stroke-linecap="round"
        stroke-width="5"
      />
      <path
        d="M84 62 H136"
        fill="none"
        stroke="rgba(255,255,255,0.55)"
        stroke-linecap="round"
        stroke-width="3"
      />
      <path
        d="M168 86 C178 82 186 86 190 94"
        fill="none"
        stroke="#f2b544"
        stroke-linecap="round"
        stroke-width="4"
        opacity="0.85"
      />
      <circle cx="192" cy="104" r="3.5" fill="#f2b544" opacity="0.8" />
      <circle cx="202" cy="91" r="2" fill="#e86a4a" opacity="0.65" />
    </svg>
    <div class="jar-caption">
      <strong>{{ points }}</strong>
      <span>罐中积分 · Lv.{{ level }}</span>
    </div>
  </div>
</template>
