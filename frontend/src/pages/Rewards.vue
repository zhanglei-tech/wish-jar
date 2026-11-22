<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { NSpin } from 'naive-ui'
import { useRouter } from 'vue-router'
import { api } from '../api'
import ChildNav from '../components/ChildNav.vue'
import EmptyState from '../components/EmptyState.vue'
import { useAuthStore } from '../stores/auth'
import type { Reward } from '../types'
import { rewardValueLabel } from '../utils'

const auth = useAuthStore()
const router = useRouter()
const rewards = ref<Reward[]>([])
const loading = ref(true)
const error = ref('')

function stockLabel(stock: number) {
  if (stock === -1) return '不限量'
  if (stock === 0) return '已兑完'
  return `还剩 ${stock} 份`
}

onMounted(async () => {
  try {
    rewards.value = await api.rewards()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '心愿商店暂时打不开'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div v-if="loading" class="loading-state">
    <n-spin size="large" />
  </div>

  <main v-else class="child-shell page-enter">
    <header class="child-header">
      <div>
        <p class="eyebrow">REWARD SHELF</p>
        <h1 class="display-title">心愿商店</h1>
        <p class="muted">挑一个想靠近的愿望，慢慢攒。</p>
      </div>
      <router-link to="/me" class="avatar-button" aria-label="我的">
        {{ auth.member?.avatar || '🌱' }}
      </router-link>
    </header>

    <div v-if="error">
      <EmptyState emoji="🫙" title="心愿商店暂时打不开" :text="error" />
    </div>
    <div v-else-if="rewards.length === 0">
      <EmptyState
        emoji="🎁"
        title="还没有上架的心愿"
        text="和家长一起想想，最近有什么值得期待的事情。"
      />
    </div>
    <div v-else class="wish-grid">
      <button
        v-for="reward in rewards"
        :key="reward.id"
        type="button"
        class="wish-card"
        @click="router.push(`/rewards/${reward.id}`)"
      >
        <span class="wish-emoji">{{ reward.emoji }}</span>
        <h3>{{ reward.title }}</h3>
        <p class="muted" style="font-size: 12px">
          {{ reward.description || '把努力换成一件开心的事。' }}
        </p>
        <div v-if="reward.is_long_term" class="progress-track">
          <div
            class="progress-fill teal"
            :style="{ width: `${Math.min(100, reward.progress_percent)}%` }"
          />
        </div>
        <div class="wish-meta">
          <span class="wish-cost">{{ reward.cost_points }} 积分</span>
          <span class="pill">{{ stockLabel(reward.stock) }}</span>
          <span v-if="reward.is_long_term && reward.locked_points" class="pill teal">
            已锁定 {{ reward.locked_points }}
          </span>
          <span v-if="reward.is_long_term && reward.estimated_days !== null" class="pill amber">
            约 {{ reward.estimated_days }} 天
          </span>
        </div>
        <div class="muted" style="font-size: 11px">
          {{ rewardValueLabel(reward.value, reward.unit) }} × {{ reward.multiplier }}
        </div>
      </button>
    </div>

    <ChildNav />
  </main>
</template>
