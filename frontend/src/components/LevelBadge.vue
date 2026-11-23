<script setup lang="ts">
import { computed, useId } from 'vue'

const props = withDefaults(
  defineProps<{
    level: number
    size?: number
  }>(),
  { size: 40 },
)

interface LevelPalette {
  bg1: string
  bg2: string
  ring: string
  glow: string
  trunk: string
  trunkLight: string
  leaf: string
  leafLight: string
  bloom: string
  fruit: string
  crystal: string
  star: string
  jar: string
  soil: string
  ray: string
  crown: string
  crownEdge: string
}

const palettes: LevelPalette[] = [
  {
    bg1: '#f8ffe9',
    bg2: '#dcefc5',
    ring: '#8dbb68',
    glow: '#d9f0b0',
    trunk: '#8a6a4a',
    trunkLight: '#c19a70',
    leaf: '#6da94d',
    leafLight: '#b3db83',
    bloom: '#ffb3c1',
    fruit: '#e86a4a',
    crystal: '#a8e8f2',
    star: '#f6cf6a',
    jar: '#fdfaf1',
    soil: '#b98b5c',
    ray: '#f2c65a',
    crown: '#f6cf6a',
    crownEdge: '#b9802d',
  },
  {
    bg1: '#e9fff9',
    bg2: '#b9e8dd',
    ring: '#3f9b8f',
    glow: '#a9f0e0',
    trunk: '#7c5c42',
    trunkLight: '#b48a67',
    leaf: '#2f8f83',
    leafLight: '#8bd5c7',
    bloom: '#ffb3c1',
    fruit: '#e86a4a',
    crystal: '#a8e8f2',
    star: '#f6cf6a',
    jar: '#f6fffc',
    soil: '#a97a50',
    ray: '#f2c65a',
    crown: '#f6cf6a',
    crownEdge: '#b9802d',
  },
  {
    bg1: '#fffaf0',
    bg2: '#ffd9b8',
    ring: '#e8925a',
    glow: '#ffe0ae',
    trunk: '#8a5c3b',
    trunkLight: '#c58d63',
    leaf: '#4f9a5e',
    leafLight: '#9dce82',
    bloom: '#ff9eb0',
    fruit: '#e86a4a',
    crystal: '#a8e8f2',
    star: '#f6cf6a',
    jar: '#fffaf1',
    soil: '#b07a4d',
    ray: '#f2b544',
    crown: '#f6cf6a',
    crownEdge: '#b9802d',
  },
  {
    bg1: '#fff4e8',
    bg2: '#ffc9a8',
    ring: '#d9734e',
    glow: '#ffcf9e',
    trunk: '#7a4a2f',
    trunkLight: '#b97a50',
    leaf: '#3f8f5a',
    leafLight: '#82c46d',
    bloom: '#ff9eb0',
    fruit: '#e85a4a',
    crystal: '#a8e8f2',
    star: '#f6cf6a',
    jar: '#fff8ee',
    soil: '#a96c3f',
    ray: '#f2b544',
    crown: '#f6cf6a',
    crownEdge: '#b9802d',
  },
  {
    bg1: '#eef8ff',
    bg2: '#c4e4ff',
    ring: '#4a8fd4',
    glow: '#b9ecff',
    trunk: '#5b6f8a',
    trunkLight: '#91a9c4',
    leaf: '#4aa3c7',
    leafLight: '#9de2f2',
    bloom: '#ffb3c1',
    fruit: '#e86a4a',
    crystal: '#8fe6ff',
    star: '#f6cf6a',
    jar: '#f4fbff',
    soil: '#8a7a66',
    ray: '#8fd6ef',
    crown: '#d9f8ff',
    crownEdge: '#4a8fd4',
  },
  {
    bg1: '#2b2a54',
    bg2: '#141a3a',
    ring: '#8a7cff',
    glow: '#b9a8ff',
    trunk: '#7a6a9a',
    trunkLight: '#b8a6d6',
    leaf: '#6fd3c7',
    leafLight: '#b8fff4',
    bloom: '#ffb3d1',
    fruit: '#ff8a6a',
    crystal: '#c4f6ff',
    star: '#fff4c2',
    jar: '#2a3158',
    soil: '#4a3f66',
    ray: '#b9a8ff',
    crown: '#fff4c2',
    crownEdge: '#8a7cff',
  },
  {
    bg1: '#3a2410',
    bg2: '#120b06',
    ring: '#ffcf5c',
    glow: '#ffe89a',
    trunk: '#9a6a3a',
    trunkLight: '#d9a765',
    leaf: '#ffd76a',
    leafLight: '#fff1b8',
    bloom: '#ffcf8a',
    fruit: '#ff9a5c',
    crystal: '#fff3c4',
    star: '#fff7cf',
    jar: '#3b2a18',
    soil: '#6b4a28',
    ray: '#ffcf5c',
    crown: '#ffe07a',
    crownEdge: '#a96b16',
  },
]

const level = computed(() => Math.min(20, Math.max(1, Math.round(props.level))))
const tier = computed(() => {
  const value = level.value
  if (value <= 4) return 0
  if (value <= 7) return 1
  if (value <= 10) return 2
  if (value <= 13) return 3
  if (value <= 16) return 4
  if (value <= 19) return 5
  return 6
})
const palette = computed(() => palettes[tier.value])
const uid = useId().replace(/:/g, '')
const bgId = `level-bg-${uid}`
const trunkId = `level-trunk-${uid}`
const clipId = `level-clip-${uid}`

const baseY = 37.5
const treeTop = computed(() => {
  if (level.value <= 4) return 34.5 - (level.value - 2) * 3
  return 28 - (level.value - 5) * 1.1
})

const sproutLeaves = computed(() => {
  if (level.value > 4) return []
  const top = treeTop.value
  const positions = [
    { x: 32, y: top - 0.6, angle: 0 },
    { x: 28.2, y: top + 2, angle: -45 },
    { x: 35.8, y: top + 2.8, angle: 45 },
  ]
  return positions.slice(0, level.value - 1)
})

const treeLeaves = computed(() => {
  if (level.value <= 4) return []
  const count = Math.min(level.value - 1, 9)
  const top = treeTop.value
  return Array.from({ length: count }, (_, index) => {
    const t = (index + 1) / (count + 1)
    const side = index % 2 === 0 ? -1 : 1
    const spread = 3.2 + 5.2 * Math.sin(Math.PI * t)
    const y = baseY - t * (baseY - top)
    const attachT = Math.max(0, t - 0.16)
    const attachY = baseY - attachT * (baseY - top)
    return {
      x: 32 + side * spread,
      y,
      angle: side * 42,
      attachY,
      curveX: 32 + side * spread * 0.45,
      curveY: attachY - 1.4,
    }
  })
})

const canopy = computed(() => {
  if (level.value < 7) return []
  const top = treeTop.value
  const scale = 0.7 + (level.value - 7) * 0.035
  return [
    { cx: 32, cy: top + 5.5, r: 7.2 * scale },
    { cx: 26.5, cy: top + 7.5, r: 5.4 * scale },
    { cx: 37.5, cy: top + 7, r: 5.8 * scale },
    { cx: 32, cy: top + 2.4, r: 5.4 * scale },
  ]
})

const bloomCount = computed(() => (level.value >= 8 ? Math.min(level.value - 7, 3) : 0))
const fruitCount = computed(() => (level.value >= 11 ? Math.min(level.value - 10, 3) : 0))
const crystalCount = computed(() => (level.value >= 14 ? Math.min(level.value - 13, 3) : 0))
const starCount = computed(() => (level.value >= 17 ? Math.min(level.value - 16, 3) : 0))
const hasRays = computed(() => level.value >= 19)
const hasCrown = computed(() => level.value >= 20)
const hasOrbit = computed(() => level.value >= 17)
const hasDoubleOrbit = computed(() => level.value >= 18)

const bloomAnchors = computed(() => {
  const top = treeTop.value
  return [
    { x: 25.5, y: top + 9 },
    { x: 38.5, y: top + 7.5 },
    { x: 32, y: top + 3.5 },
  ]
})
const fruitAnchors = computed(() => {
  const top = treeTop.value
  return [
    { x: 27, y: top + 13 },
    { x: 37.5, y: top + 12 },
    { x: 31.5, y: top + 8 },
  ]
})
const crystalAnchors = computed(() => {
  const top = treeTop.value
  return [
    { x: 24, y: top + 4 },
    { x: 40, y: top + 5 },
    { x: 32, y: top - 1.5 },
  ]
})
const starAnchors = computed(() => {
  const top = treeTop.value
  return [
    { x: 21.5, y: top + 10 },
    { x: 42.5, y: top + 8 },
    { x: 32, y: top - 5 },
  ]
})

const bloomPetals = Array.from({ length: 5 }, (_, index) => {
  const angle = (index * 72 * Math.PI) / 180
  return {
    cx: Math.cos(angle) * 2.3,
    cy: Math.sin(angle) * 2.3,
  }
})

const rays = computed(() =>
  Array.from({ length: 10 }, (_, index) => {
    const angle = (index * 36 * Math.PI) / 180
    return {
      x1: 32 + Math.cos(angle) * 20,
      y1: 32 + Math.sin(angle) * 20,
      x2: 32 + Math.cos(angle) * 29,
      y2: 32 + Math.sin(angle) * 29,
    }
  }),
)

const backgroundDots = [
  { cx: 14, cy: 22, r: 0.75 },
  { cx: 50, cy: 18, r: 0.9 },
  { cx: 17, cy: 45, r: 0.6 },
  { cx: 48, cy: 43, r: 0.7 },
  { cx: 10, cy: 34, r: 0.55 },
  { cx: 53, cy: 32, r: 0.55 },
]
</script>

<template>
  <svg
    class="level-badge-svg"
    :width="size"
    :height="size"
    viewBox="0 0 64 64"
    role="img"
    :aria-label="`Lv.${level} 徽章`"
    focusable="false"
  >
    <defs>
      <radialGradient :id="bgId" cx="32%" cy="24%" r="82%">
        <stop offset="0%" :stop-color="palette.bg1" />
        <stop offset="100%" :stop-color="palette.bg2" />
      </radialGradient>
      <linearGradient :id="trunkId" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" :stop-color="palette.trunkLight" />
        <stop offset="100%" :stop-color="palette.trunk" />
      </linearGradient>
      <clipPath :id="clipId">
        <circle cx="32" cy="32" r="29" />
      </clipPath>
    </defs>

    <circle cx="32" cy="32" r="30" :fill="`url(#${bgId})`" :stroke="palette.ring" stroke-width="1.15" />
    <circle
      v-if="tier >= 1"
      cx="32"
      cy="32"
      r="27.4"
      fill="none"
      :stroke="palette.ring"
      stroke-width="0.5"
      opacity="0.55"
    />
    <circle
      v-if="tier >= 2"
      cx="32"
      cy="32"
      r="29.1"
      fill="none"
      :stroke="palette.ring"
      stroke-width="1.5"
      stroke-dasharray="1 4"
      opacity="0.55"
    />
    <circle
      v-if="tier >= 5"
      cx="32"
      cy="32"
      r="30"
      fill="none"
      :stroke="palette.glow"
      stroke-width="4"
      opacity="0.18"
    />

    <g :clip-path="`url(#${clipId})`">
      <g v-if="hasRays" :stroke="palette.ray" stroke-width="0.8" stroke-linecap="round" opacity="0.4">
        <line
          v-for="(ray, index) in rays"
          :key="`ray-${index}`"
          :x1="ray.x1"
          :y1="ray.y1"
          :x2="ray.x2"
          :y2="ray.y2"
        />
      </g>

      <g v-if="hasOrbit" fill="none" :stroke="palette.glow" stroke-width="0.75" stroke-dasharray="2 3" opacity="0.7">
        <ellipse cx="32" cy="32" rx="27" ry="10.5" transform="rotate(-24 32 32)" />
        <ellipse
          v-if="hasDoubleOrbit"
          cx="32"
          cy="32"
          rx="25"
          ry="8.5"
          transform="rotate(26 32 32)"
          opacity="0.65"
        />
      </g>

      <g v-if="tier >= 5" :fill="palette.star" opacity="0.7">
        <circle
          v-for="(dot, index) in backgroundDots"
          :key="`dot-${index}`"
          :cx="dot.cx"
          :cy="dot.cy"
          :r="dot.r"
        />
      </g>

      <g v-if="canopy.length" :fill="palette.leafLight" opacity="0.16">
        <circle
          v-for="(blob, index) in canopy"
          :key="`canopy-${index}`"
          :cx="blob.cx"
          :cy="blob.cy"
          :r="blob.r"
        />
      </g>

      <!-- 心愿罐 -->
      <g>
        <path
          d="M24 41.5 h16 a2 2 0 0 1 2 2 v6 a4.4 4.4 0 0 1 -4.4 4.4 h-11.2 a4.4 4.4 0 0 1 -4.4 -4.4 v-6 a2 2 0 0 1 2 -2 z"
          :fill="palette.jar"
          fill-opacity="0.78"
          :stroke="palette.ring"
          stroke-width="1.1"
        />
        <rect x="27" y="37.8" width="10" height="4.4" rx="1.8" :fill="palette.jar" fill-opacity="0.9" :stroke="palette.ring" stroke-width="1" />
        <rect x="26" y="36.4" width="12" height="2.4" rx="1.2" :fill="palette.bg1" :stroke="palette.ring" stroke-width="0.9" />
        <ellipse cx="32" cy="50.8" rx="7.2" ry="2.2" :fill="palette.soil" opacity="0.85" />
        <path d="M23.8 45.5 q1.2 2.4 0 4.6" fill="none" stroke="#ffffff" stroke-width="0.8" stroke-linecap="round" opacity="0.55" />
      </g>

      <!-- 树 / 嫩芽 -->
      <g v-if="level <= 4" fill="none" :stroke="`url(#${trunkId})`" stroke-width="2" stroke-linecap="round">
        <path :d="`M32 ${baseY} C30.6 ${baseY - 1.8} 33.2 ${treeTop + 1.6} 32 ${treeTop}`" />
      </g>
      <g v-else fill="none" :stroke="`url(#${trunkId})`" stroke-width="2.1" stroke-linecap="round">
        <path
          v-for="(leaf, index) in treeLeaves"
          :key="`branch-${index}`"
          :d="`M32 ${leaf.attachY} Q${leaf.curveX} ${leaf.curveY} ${leaf.x} ${leaf.y}`"
          stroke-width="1.25"
          opacity="0.9"
        />
        <path
          :d="`M32 ${baseY} C30.4 ${baseY - 5} 33.6 ${treeTop + 5} 32 ${treeTop}`"
          stroke-width="2.25"
        />
      </g>

      <g v-if="level <= 4">
        <ellipse
          v-for="(leaf, index) in sproutLeaves"
          :key="`sprout-${index}`"
          :cx="leaf.x"
          :cy="leaf.y"
          rx="3.4"
          ry="1.95"
          :fill="palette.leaf"
          :transform="`rotate(${leaf.angle} ${leaf.x} ${leaf.y})`"
        />
      </g>
      <g v-else>
        <ellipse
          v-for="(leaf, index) in treeLeaves"
          :key="`leaf-${index}`"
          :cx="leaf.x"
          :cy="leaf.y"
          rx="3.5"
          ry="1.95"
          :fill="index % 3 === 0 ? palette.leafLight : palette.leaf"
          :transform="`rotate(${leaf.angle} ${leaf.x} ${leaf.y})`"
        />
      </g>

      <!-- 花 -->
      <g v-for="(anchor, index) in bloomAnchors.slice(0, bloomCount)" :key="`bloom-${index}`">
        <circle
          v-for="(petal, petalIndex) in bloomPetals"
          :key="`petal-${petalIndex}`"
          :cx="anchor.x + petal.cx"
          :cy="anchor.y + petal.cy"
          r="1.75"
          :fill="palette.bloom"
          opacity="0.95"
        />
        <circle :cx="anchor.x" :cy="anchor.y" r="1.25" :fill="palette.star" />
      </g>

      <!-- 果实 -->
      <g v-for="(anchor, index) in fruitAnchors.slice(0, fruitCount)" :key="`fruit-${index}`">
        <circle :cx="anchor.x" :cy="anchor.y" r="2.1" :fill="palette.fruit" />
        <circle :cx="anchor.x - 0.6" :cy="anchor.y - 0.7" r="0.65" fill="#ffffff" opacity="0.65" />
      </g>

      <!-- 晶体 -->
      <g v-for="(anchor, index) in crystalAnchors.slice(0, crystalCount)" :key="`crystal-${index}`">
        <path
          :d="`M${anchor.x} ${anchor.y - 3.4} L${anchor.x + 2.3} ${anchor.y} L${anchor.x} ${anchor.y + 3.4} L${anchor.x - 2.3} ${anchor.y} Z`"
          :fill="palette.crystal"
          :stroke="palette.ring"
          stroke-width="0.55"
        />
        <path
          :d="`M${anchor.x} ${anchor.y - 3.4} L${anchor.x + 0.8} ${anchor.y} L${anchor.x} ${anchor.y + 3.4}`"
          fill="none"
          stroke="#ffffff"
          stroke-width="0.5"
          opacity="0.7"
        />
      </g>

      <!-- 星辉 -->
      <g v-for="(anchor, index) in starAnchors.slice(0, starCount)" :key="`star-${index}`">
        <path
          :d="`M${anchor.x} ${anchor.y - 4.2} L${anchor.x + 1.1} ${anchor.y - 1.1} L${anchor.x + 4.2} ${anchor.y} L${anchor.x + 1.1} ${anchor.y + 1.1} L${anchor.x} ${anchor.y + 4.2} L${anchor.x - 1.1} ${anchor.y + 1.1} L${anchor.x - 4.2} ${anchor.y} L${anchor.x - 1.1} ${anchor.y - 1.1} Z`"
          :fill="palette.star"
          opacity="0.95"
        />
        <circle :cx="anchor.x" :cy="anchor.y" r="0.9" fill="#ffffff" opacity="0.9" />
      </g>

      <!-- 王冠 -->
      <g v-if="hasCrown" :transform="`translate(32 ${treeTop - 5.2})`">
        <circle cx="0" cy="-1" r="10.5" :fill="palette.glow" opacity="0.2" />
        <path
          d="M-7.2 3 L-8.2 -3.2 L-3.2 -1 L0 -6.4 L3.2 -1 L8.2 -3.2 L7.2 3 Z"
          :fill="palette.crown"
          :stroke="palette.crownEdge"
          stroke-width="0.65"
          stroke-linejoin="round"
        />
        <circle cx="-5" cy="1" r="0.95" :fill="palette.crownEdge" />
        <circle cx="0" cy="0.4" r="1.15" :fill="palette.crownEdge" />
        <circle cx="5" cy="1" r="0.95" :fill="palette.crownEdge" />
      </g>
    </g>

    <circle cx="32" cy="32" r="30" fill="none" :stroke="palette.ring" stroke-width="0.55" opacity="0.45" />
  </svg>
</template>

<style scoped>
.level-badge-svg {
  display: block;
  flex: none;
}
</style>
