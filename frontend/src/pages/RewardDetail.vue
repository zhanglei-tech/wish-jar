<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  NButton,
  NInputNumber,
  NSpin,
  useDialog,
  useMessage,
} from 'naive-ui'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import ChildNav from '../components/ChildNav.vue'
import EmptyState from '../components/EmptyState.vue'
import type { PointSummary, Reward } from '../types'
import {
  formatDate,
  lockStatusLabel,
  rewardValueLabel,
} from '../utils'

const route = useRoute()
const router = useRouter()
const dialog = useDialog()
const message = useMessage()

const reward = ref<Reward | null>(null)
const points = ref<PointSummary | null>(null)
const loading = ref(true)
const error = ref('')
const lockAmount = ref<number | null>(null)
const locking = ref(false)
const redeeming = ref(false)

const rewardId = computed(() => Number(route.params.id))

const canRedeem = computed(() => {
  if (!reward.value || !points.value) return false
  if (!reward.value.active || reward.value.stock === 0) return false
  return (
    points.value.available + reward.value.locked_points >=
    reward.value.cost_points
  )
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [rewardData, pointData] = await Promise.all([
      api.reward(rewardId.value),
      api.points(),
    ])
    reward.value = rewardData
    points.value = pointData
  } catch (err) {
    error.value = err instanceof Error ? err.message : '这个心愿暂时打不开'
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function lockSavings() {
  if (!reward.value || !lockAmount.value) {
    message.warning('先填入想锁定的积分')
    return
  }
  locking.value = true
  try {
    await api.lockSavings(reward.value.id, lockAmount.value, '为心愿锁定')
    message.success('已锁定，这部分积分会先留给这个心愿')
    lockAmount.value = null
    await load()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '锁定失败，请再试一次')
  } finally {
    locking.value = false
  }
}

function redeem() {
  if (!reward.value || !points.value) return
  dialog.warning({
    title: '申请兑换这个心愿？',
    content: `兑换需要 ${reward.value.cost_points} 积分，提交后由家长审核。审核通过前不会扣积分。`,
    positiveText: '申请兑换',
    negativeText: '再想想',
    onPositiveClick: async () => {
      if (!reward.value) return
      redeeming.value = true
      try {
        await api.requestRedemption(reward.value.id)
        message.success('兑换申请已提交，等家长确认')
        await load()
      } catch (err) {
        message.error(
          err instanceof Error ? err.message : '申请失败，请再试一次',
        )
      } finally {
        redeeming.value = false
      }
    },
  })
}
</script>

<template>
  <div v-if="loading" class="loading-state">
    <n-spin size="large" />
  </div>

  <main v-else class="detail-shell page-enter">
    <router-link to="/rewards" class="back-link">← 回到心愿商店</router-link>

    <div v-if="error || !reward">
      <EmptyState
        emoji="🫙"
        title="这个心愿暂时打不开"
        :text="error || '它可能已经被收起来了。'"
      />
    </div>

    <template v-else>
      <section class="reward-hero">
        <div class="big-emoji">{{ reward.emoji }}</div>
        <div>
          <p class="eyebrow">{{ reward.is_long_term ? 'LONG-TERM WISH' : 'REWARD' }}</p>
          <h1>{{ reward.title }}</h1>
          <p>{{ reward.description || '把努力换成一件开心的事。' }}</p>
          <div class="price-box">
            <strong>{{ reward.cost_points }}</strong>
            <span>积分可兑换</span>
            <span class="pill" :class="reward.stock === 0 ? 'accent' : 'teal'">
              {{
                reward.stock === -1
                  ? '不限量'
                  : reward.stock === 0
                    ? '已兑完'
                    : `还剩 ${reward.stock} 份`
              }}
            </span>
          </div>
        </div>
      </section>

      <section class="detail-card">
        <h2>兑换方式</h2>
        <div class="formula">
          {{ rewardValueLabel(reward.value, reward.unit) }}
          ×
          {{ reward.multiplier }}
          =
          {{ reward.cost_points }} 积分
        </div>
        <p class="muted" style="margin-top: 9px; font-size: 12px">
          倍率越高，同样价值需要更多积分。提交申请时会把当前价格记下来，之后改价不影响已经提交的申请。
        </p>
      </section>

      <section v-if="reward.is_long_term" class="detail-card">
        <div class="panel-head">
          <div>
            <h2>心愿进度</h2>
            <p class="hint">
              锁定储蓄只是把积分先留给这个心愿，不会减少总积分。
            </p>
          </div>
          <span class="pill teal">已锁定 {{ reward.locked_points }}</span>
        </div>

        <div class="progress-track">
          <div
            class="progress-fill teal"
            :style="{ width: `${Math.min(100, reward.progress_percent)}%` }"
          />
        </div>
        <div class="wish-meta" style="margin-top: 8px">
          <span class="muted" style="font-size: 12px">
            还差 {{ reward.remaining_points }} 积分
          </span>
          <span v-if="reward.estimated_days !== null" class="pill amber">
            按最近节奏约 {{ reward.estimated_days }} 天
          </span>
        </div>

        <div class="lock-form">
          <n-input-number
            v-model:value="lockAmount"
            :min="1"
            :max="points?.available ?? 0"
            placeholder="锁定多少积分"
            style="width: 100%"
          />
          <n-button
            type="primary"
            secondary
            :loading="locking"
            :disabled="!points || points.available <= 0"
            @click="lockSavings"
          >
            锁定储蓄
          </n-button>
        </div>
        <p class="muted" style="margin-top: 6px; font-size: 11px">
          当前可用 {{ points?.available ?? 0 }} 积分。解锁需要请家长操作。
        </p>

        <div v-if="reward.locks.length" class="lock-list">
          <div v-for="lock in reward.locks" :key="lock.id" class="lock-row">
            <span>
              {{ formatDate(lock.created_at) }} · {{ lock.amount }} 积分
            </span>
            <span class="pill teal">{{ lockStatusLabel(lock.status) }}</span>
          </div>
        </div>
      </section>

      <section class="detail-card">
        <div class="panel-head">
          <div>
            <h2>准备好兑换了吗？</h2>
            <p class="hint">
              申请后由家长审核，通过时才会扣积分和库存。
            </p>
          </div>
        </div>
        <div class="wish-meta" style="margin-bottom: 13px">
          <span class="pill amber">可用 {{ points?.available ?? 0 }}</span>
          <span v-if="reward.is_long_term" class="pill teal">
            锁定 {{ reward.locked_points }}
          </span>
          <span class="pill">共需 {{ reward.cost_points }}</span>
        </div>
        <n-button
          type="primary"
          size="large"
          block
          :disabled="!canRedeem || redeeming"
          :loading="redeeming"
          @click="redeem"
        >
          {{ reward.stock === 0 ? '已经兑完了' : '申请兑换' }}
        </n-button>
        <p
          v-if="!canRedeem && reward.stock !== 0"
          class="muted"
          style="margin-top: 7px; font-size: 12px; text-align: center"
        >
          积分还差一点，继续完成任务就能靠近它。
        </p>
      </section>

      <ChildNav />
    </template>
  </main>
</template>
