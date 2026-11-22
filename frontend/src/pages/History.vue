<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { NSpin } from 'naive-ui'
import { api } from '../api'
import ChildNav from '../components/ChildNav.vue'
import EmptyState from '../components/EmptyState.vue'
import { useAuthStore } from '../stores/auth'
import type { PointSummary, Redemption } from '../types'
import {
  formatDateTime,
  redemptionStatusLabel,
  signedPoints,
} from '../utils'

const auth = useAuthStore()
const activeTab = ref<'points' | 'redemptions'>('points')
const points = ref<PointSummary | null>(null)
const redemptions = ref<Redemption[]>([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const [pointData, redemptionData] = await Promise.all([
      api.points(undefined, 100),
      api.redemptions({ limit: 100 }),
    ])
    points.value = pointData
    redemptions.value = redemptionData
  } catch (err) {
    error.value = err instanceof Error ? err.message : '足迹暂时打不开'
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
        <p class="eyebrow">YOUR LITTLE TRAIL</p>
        <h1 class="display-title">积分足迹</h1>
        <p class="muted">每一分，都是你认真做过的事。</p>
      </div>
      <router-link to="/me" class="avatar-button" aria-label="我的">
        {{ auth.member?.avatar || '🌱' }}
      </router-link>
    </header>

    <div v-if="error">
      <EmptyState emoji="🫙" title="足迹暂时打不开" :text="error" />
    </div>

    <template v-else>
      <div class="history-tabs">
        <button
          type="button"
          :class="{ active: activeTab === 'points' }"
          @click="activeTab = 'points'"
        >
          积分记录
        </button>
        <button
          type="button"
          :class="{ active: activeTab === 'redemptions' }"
          @click="activeTab = 'redemptions'"
        >
          兑换记录
        </button>
      </div>

      <section v-if="activeTab === 'points'" class="detail-card">
        <div v-if="!points || points.transactions.length === 0">
          <EmptyState
            emoji="🌱"
            title="还没有积分记录"
            text="完成第一个任务，这里就会留下第一行足迹。"
          />
        </div>
        <div v-else>
          <div
            v-for="transaction in points.transactions"
            :key="transaction.id"
            class="transaction-row"
          >
            <div class="transaction-main">
              <strong>{{ transaction.note }}</strong>
              <span>
                {{ formatDateTime(transaction.created_at) }} ·
                {{ transaction.kind === 'task' ? '任务' : transaction.kind === 'redeem' ? '兑换' : '调整' }}
              </span>
            </div>
            <span
              class="transaction-delta"
              :class="transaction.delta > 0 ? 'positive' : 'negative'"
            >
              {{ signedPoints(transaction.delta) }}
            </span>
          </div>
        </div>
      </section>

      <section v-else class="detail-card">
        <div v-if="redemptions.length === 0">
          <EmptyState
            emoji="🎁"
            title="还没有兑换记录"
            text="等积分攒够，去心愿商店挑一个喜欢的愿望。"
          />
        </div>
        <div v-else>
          <div
            v-for="redemption in redemptions"
            :key="redemption.id"
            class="transaction-row"
          >
            <div class="transaction-main">
              <strong>{{ redemption.reward_emoji }} {{ redemption.reward_title }}</strong>
              <span>
                {{ formatDateTime(redemption.requested_at) }} ·
                {{ redemption.cost_points }} 积分
              </span>
            </div>
            <span
              class="pill"
              :class="
                redemption.status === 'fulfilled'
                  ? 'teal'
                  : redemption.status === 'rejected'
                    ? 'accent'
                    : 'amber'
              "
            >
              {{ redemptionStatusLabel(redemption.status) }}
            </span>
          </div>
        </div>
      </section>
    </template>

    <ChildNav />
  </main>
</template>
