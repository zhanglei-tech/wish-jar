<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { NButton, NSpin, useMessage } from 'naive-ui'
import { api } from '../api'
import ChildNav from '../components/ChildNav.vue'
import EmptyState from '../components/EmptyState.vue'
import ParentNav from '../components/ParentNav.vue'
import { useAuthStore } from '../stores/auth'
import type { Stats, StatsPeriod } from '../types'

const auth = useAuthStore()
const message = useMessage()

const isParent = computed(() => auth.member?.role === 'parent')
const stats = ref<Stats | null>(null)
const loading = ref(true)
const error = ref('')
const period = ref<StatsPeriod>('week')
const childId = ref<number | null>(null)
const children = ref<{ id: number; name: string; avatar: string }[]>([])

const periods: { label: string; value: StatsPeriod }[] = [
  { label: '本周', value: 'week' },
  { label: '本月', value: 'month' },
  { label: '本季度', value: 'quarter' },
  { label: '本年', value: 'year' },
]

const maxAbs = computed(() => {
  const values = stats.value?.buckets.map((bucket) => Math.abs(bucket.net_points)) ?? []
  return Math.max(1, ...values)
})

const statusLabels: Record<string, string> = {
  pending: '待审核',
  approved: '已通过',
  rejected: '已驳回',
  fulfilled: '已兑现',
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    stats.value = await api.stats(
      period.value,
      isParent.value ? childId.value ?? undefined : undefined,
    )
  } catch (err) {
    error.value = err instanceof Error ? err.message : '统计暂时打不开'
  } finally {
    loading.value = false
  }
}

async function init() {
  if (isParent.value) {
    try {
      const dashboard = await api.parentDashboard()
      children.value = dashboard.children.map((child) => ({
        id: child.member.id,
        name: child.member.name,
        avatar: child.member.avatar,
      }))
      childId.value = children.value[0]?.id ?? null
    } catch {
      // The error is surfaced by load().
    }
  }
  await load()
}

onMounted(init)
watch([period, childId], load)

function exportCsv() {
  if (!isParent.value) return
  const url = api.statsExportUrl(period.value, childId.value ?? undefined)
  const link = document.createElement('a')
  link.href = url
  link.download = ''
  document.body.appendChild(link)
  link.click()
  link.remove()
  message.success('CSV 已开始下载')
}
</script>

<template>
  <div v-if="loading" class="loading-state">
    <n-spin size="large" />
  </div>

  <main v-else class="child-shell page-enter" :class="{ 'parent-shell': isParent }">
    <ParentNav v-if="isParent" />
    <header v-else class="child-header">
      <div>
        <p class="eyebrow">LITTLE CHARTS</p>
        <h1 class="display-title">成长统计</h1>
        <p class="muted">看看这段时间，心愿罐是怎么长大的。</p>
      </div>
      <router-link to="/me" class="avatar-button" aria-label="我的">
        {{ auth.member?.avatar || '🌱' }}
      </router-link>
    </header>

    <header v-if="isParent" class="parent-title">
      <p class="eyebrow">FAMILY STATS</p>
      <h1>成长统计</h1>
      <p>按周期查看积分趋势、任务完成率和兑换记录。</p>
    </header>

    <div class="stats-toolbar">
      <div class="period-tabs">
        <button
          v-for="item in periods"
          :key="item.value"
          type="button"
          :class="{ active: period === item.value }"
          @click="period = item.value"
        >
          {{ item.label }}
        </button>
      </div>
      <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap">
        <select v-if="isParent" v-model="childId" class="native-input" style="width: auto">
          <option v-for="child in children" :key="child.id" :value="child.id">
            {{ child.avatar }} {{ child.name }}
          </option>
        </select>
        <n-button v-if="isParent" tertiary @click="exportCsv">导出 CSV</n-button>
      </div>
    </div>

    <div v-if="error">
      <EmptyState emoji="📊" title="统计暂时打不开" :text="error" />
    </div>

    <template v-else-if="stats">
      <section class="detail-card">
        <div class="panel-head">
          <div>
            <h2>{{ stats.label }}</h2>
            <p class="hint">
              {{ stats.start_date }} 至 {{ stats.end_date }} · {{ stats.child_name }}
            </p>
          </div>
          <span class="pill" :class="stats.net_points >= 0 ? 'teal' : 'accent'">
            净变化 {{ stats.net_points > 0 ? '+' : '' }}{{ stats.net_points }}
          </span>
        </div>

        <div class="stats-grid">
          <div class="stat-tile">
            <strong>+{{ stats.task_points }}</strong>
            <span>任务获得</span>
          </div>
          <div class="stat-tile">
            <strong>+{{ stats.bonus_points }}</strong>
            <span>连续奖励</span>
          </div>
          <div class="stat-tile">
            <strong>-{{ stats.redeemed_points }}</strong>
            <span>兑换扣除</span>
          </div>
          <div class="stat-tile">
            <strong>{{ stats.adjusted_points > 0 ? '+' : '' }}{{ stats.adjusted_points }}</strong>
            <span>家长调整</span>
          </div>
        </div>
      </section>

      <EmptyState
        v-if="!stats.has_data"
        emoji="🌱"
        title="这个周期还没有记录"
        text="换一个周期看看，或者从完成一个小任务开始。"
      />

      <template v-else>
        <section class="detail-card">
          <div class="panel-head">
            <div>
              <h2>积分趋势</h2>
              <p class="hint">每个柱子的高度代表净变化</p>
            </div>
          </div>
          <div class="chart-row">
            <div
              v-for="bucket in stats.buckets"
              :key="bucket.label"
              class="chart-column"
              :title="`${bucket.label}：任务 +${bucket.task_points}，连续 +${bucket.bonus_points}，兑换 -${bucket.redeemed_points}，调整 ${bucket.adjusted_points}`"
            >
              <span class="chart-value">{{ bucket.net_points }}</span>
              <div class="chart-space">
                <div
                  class="chart-bar"
                  :class="bucket.net_points >= 0 ? 'positive' : 'negative'"
                  :style="{
                    height: `${Math.max(4, Math.abs(bucket.net_points) * 100 / maxAbs)}%`,
                  }"
                />
              </div>
              <span class="chart-label">{{ bucket.label }}</span>
            </div>
          </div>
        </section>

        <section class="detail-card">
          <div class="panel-head">
            <div>
              <h2>任务完成率</h2>
              <p class="hint">已通过提交 ÷ 应完成次数</p>
            </div>
            <span class="pill amber">{{ stats.task_completion.percent }}%</span>
          </div>
          <div class="progress-track">
            <div
              class="progress-fill amber"
              :style="{ width: `${Math.min(100, stats.task_completion.percent)}%` }"
            />
          </div>
          <p class="muted" style="font-size: 12px; margin-top: 8px">
            {{ stats.task_completion.approved }} / {{ stats.task_completion.expected }} 次完成
          </p>
        </section>

        <section class="detail-card">
          <div class="panel-head">
            <div>
              <h2>兑换记录</h2>
              <p class="hint">这个周期提交的兑换申请</p>
            </div>
            <span class="pill">{{ stats.redemption_count }} 次</span>
          </div>
          <div class="wish-meta">
            <span class="pill teal">消耗 {{ stats.redemption_points }} 积分</span>
            <span
              v-for="(count, status) in stats.redemption_statuses"
              :key="status"
              class="pill"
            >
              {{ statusLabels[status] ?? status }} {{ count }}
            </span>
          </div>
          <p
            v-if="stats.redemption_count === 0"
            class="muted"
            style="font-size: 12px; margin-top: 10px"
          >
            这个周期还没有兑换申请。
          </p>
        </section>
      </template>
    </template>

    <ChildNav v-if="!isParent" />
  </main>
</template>
