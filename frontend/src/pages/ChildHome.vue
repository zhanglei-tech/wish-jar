<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NSpin, useMessage } from 'naive-ui'
import { useRouter } from 'vue-router'
import { api } from '../api'
import ChildNav from '../components/ChildNav.vue'
import EmptyState from '../components/EmptyState.vue'
import TaskSubmitModal from '../components/TaskSubmitModal.vue'
import WishJar from '../components/WishJar.vue'
import type { ChildHome, TodayTask } from '../types'
import {
  formatDateTime,
  greeting,
  taskTypeLabel,
  todayLabel,
} from '../utils'

const router = useRouter()
const message = useMessage()

const home = ref<ChildHome | null>(null)
const loading = ref(true)
const error = ref('')
const submitting = ref(false)
const showSubmit = ref(false)
const activeTask = ref<TodayTask | null>(null)

const doneCount = computed(
  () => home.value?.today_tasks.filter((task) => task.status === 'done').length ?? 0,
)

const greetingText = computed(() => {
  const name = home.value?.member.name ?? ''
  return name ? `${greeting()}，${name}` : greeting()
})

const levelPercent = computed(() => {
  const current = home.value
  if (!current) return 0
  if (current.next_level_points <= 0) return 100
  const span = current.level_progress + current.next_level_points
  if (span <= 0) return 0
  return Math.round((current.level_progress * 100) / span)
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    home.value = await api.childHome()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '心愿罐暂时打不开'
  } finally {
    loading.value = false
  }
}

onMounted(load)

function taskClass(task: TodayTask) {
  return task.status
}

function statusText(task: TodayTask) {
  if (task.status === 'done') return '已存入'
  if (task.status === 'pending') return '等家长看看'
  if (task.status === 'rejected') return '再试一次'
  return '去完成 →'
}

function taskEmoji(task: TodayTask) {
  if (task.status === 'done') return '✅'
  if (task.requires_photo) return '📷'
  if (task.status === 'pending') return '⏳'
  return '✦'
}

function openTask(task: TodayTask) {
  if (task.status === 'done' || task.status === 'pending') return
  activeTask.value = task
  showSubmit.value = true
}

async function submit(note: string, photo: File | null) {
  if (!activeTask.value) return
  submitting.value = true
  try {
    await api.submitTask(activeTask.value.id, note, photo)
    message.success('已提交，等家长看看就有积分啦')
    showSubmit.value = false
    await load()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '提交失败，请再试一次')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div v-if="loading" class="loading-state">
    <n-spin size="large" />
  </div>

  <main v-else-if="home" class="child-shell page-enter">
    <header class="child-header">
      <div>
        <p class="eyebrow">{{ todayLabel() }}</p>
        <h1 class="display-title">{{ greetingText }}</h1>
        <p class="muted">今天也往心愿罐里，放一点小小的努力吧。</p>
      </div>
      <router-link to="/me" class="avatar-button" aria-label="我的">
        {{ home.member.avatar }}
      </router-link>
    </header>

    <section class="hero-grid">
      <WishJar
        :points="home.balance"
        :level="home.level"
        :progress="levelPercent"
      />
      <div class="hero-copy">
        <div class="level-row">
          <span class="level-badge">Lv.{{ home.level }}</span>
          <span class="muted">
            {{ home.next_level_points > 0 ? `再攒 ${home.next_level_points} 分升级` : '已经是最高等级' }}
          </span>
        </div>
        <h2>把今天的小努力，<br />存进心愿罐里。</h2>
        <div class="mini-stats">
          <div class="mini-stat">
            <strong>{{ home.available }}</strong>
            <span>可用积分</span>
          </div>
          <div class="mini-stat">
            <strong>{{ home.locked }}</strong>
            <span>心愿锁定</span>
          </div>
          <div class="mini-stat">
            <strong>{{ home.streak_days }}</strong>
            <span>连续打卡</span>
          </div>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="section-heading">
        <h2>今天要做的事</h2>
        <span class="muted">{{ doneCount }} / {{ home.today_tasks.length }} 完成</span>
      </div>

      <div v-if="home.today_tasks.length === 0">
        <EmptyState
          emoji="🌤️"
          title="今天没有安排任务"
          text="休息一下，或者去心愿商店看看想靠近的愿望。"
        />
      </div>
      <div v-else class="task-list">
        <button
          v-for="task in home.today_tasks"
          :key="task.id"
          type="button"
          class="task-card"
          :class="taskClass(task)"
          @click="openTask(task)"
        >
          <span class="task-emoji">{{ taskEmoji(task) }}</span>
          <div class="task-main">
            <h3>{{ task.title }}</h3>
            <p>{{ task.description || '完成后就能获得积分' }}</p>
            <div class="task-meta">
              <span class="points">+{{ task.points }} 积分</span>
              <span class="pill">{{ taskTypeLabel(task.task_type) }}</span>
              <span v-if="task.goal_title" class="pill teal">{{ task.goal_title }}</span>
              <span v-if="task.reward_title" class="pill amber">专属 {{ task.reward_title }}</span>
              <span v-if="task.bonus_active" class="pill teal">连续奖励生效</span>
              <span
                v-else-if="task.task_type === 'daily' && task.streak_bonus_percent > 0"
                class="pill"
              >
                连续 {{ task.streak_threshold_days }} 天 +{{ task.streak_bonus_percent }}%
              </span>
            </div>
          </div>
          <span class="task-action">{{ statusText(task) }}</span>
        </button>
      </div>
    </section>

    <section v-if="home.goals.length" class="section">
      <div class="section-heading">
        <h2>正在靠近的目标</h2>
        <router-link to="/rewards" class="text-link">心愿商店 →</router-link>
      </div>
      <div class="task-list">
        <article v-for="goal in home.goals" :key="goal.id" class="goal-card">
          <div class="goal-top">
            <div class="goal-title">
              <img v-if="goal.icon_url" :src="goal.icon_url" class="goal-icon" alt="" />
              <span v-else class="emoji">{{ goal.emoji }}</span>
              {{ goal.title }}
            </div>
            <span class="pill amber">{{ goal.progress_percent }}%</span>
          </div>
          <div class="progress-track">
            <div
              class="progress-fill"
              :style="{ width: `${Math.min(100, goal.progress_percent)}%` }"
            />
          </div>
          <div class="muted" style="font-size: 12px">
            {{ goal.progress_value }} / {{ goal.target_value }}
            {{ goal.progress_mode === 'points' ? '积分' : '次' }} ·
            {{ goal.task_count }} 个任务
          </div>
          <div v-if="goal.stages.length" class="wish-meta">
            <span
              v-for="stage in goal.stages"
              :key="stage.id"
              class="pill"
              :class="stage.achieved ? 'teal' : ''"
            >
              {{ stage.badge_emoji }} {{ stage.threshold_value }}
            </span>
          </div>
          <p v-if="goal.next_stage" class="muted" style="font-size: 12px">
            下一阶段「{{ goal.next_stage.badge_name }}」还差
            {{ goal.next_stage.threshold_value - goal.progress_value }}
            {{ goal.progress_mode === 'points' ? '积分' : '次' }}
          </p>
          <p v-else-if="goal.badge_name" class="muted" style="font-size: 12px">
            完成可得成就「{{ goal.badge_name }}」
          </p>
        </article>
      </div>
    </section>

    <section v-if="home.long_term_rewards.length" class="section">
      <div class="section-heading">
        <h2>慢慢长大的心愿</h2>
        <span class="muted">锁定储蓄，不花掉</span>
      </div>
      <div class="wish-grid">
        <button
          v-for="reward in home.long_term_rewards"
          :key="reward.id"
          type="button"
          class="wish-card"
          @click="router.push(`/rewards/${reward.id}`)"
        >
          <span class="wish-emoji">{{ reward.emoji }}</span>
          <h3>{{ reward.title }}</h3>
          <div class="progress-track">
            <div
              class="progress-fill teal"
              :style="{ width: `${Math.min(100, reward.progress_percent)}%` }"
            />
          </div>
          <div class="wish-meta">
            <span class="wish-cost">{{ reward.remaining_points }} 分</span>
            <span class="pill teal">已锁定 {{ reward.locked_points }}</span>
            <span v-if="reward.matched_points" class="pill amber">
              家长配捐 {{ reward.matched_points }}
            </span>
            <span v-if="reward.estimated_days !== null" class="pill">
              约 {{ reward.estimated_days }} 天
            </span>
          </div>
        </button>
      </div>
    </section>

    <section class="section">
      <div class="section-heading">
        <h2>最近的积分足迹</h2>
        <router-link to="/history" class="text-link">全部足迹 →</router-link>
      </div>
      <div v-if="home.recent_transactions.length === 0">
        <EmptyState
          emoji="🌱"
          title="还没有积分记录"
          text="完成第一个任务，心愿罐就会开始长大。"
        />
      </div>
      <div v-else>
        <div
          v-for="transaction in home.recent_transactions"
          :key="transaction.id"
          class="transaction-row"
        >
          <div class="transaction-main">
            <strong>{{ transaction.note }}</strong>
            <span>{{ formatDateTime(transaction.created_at) }}</span>
          </div>
          <span
            class="transaction-delta"
            :class="transaction.delta > 0 ? 'positive' : 'negative'"
          >
            {{ transaction.delta > 0 ? '+' : '' }}{{ transaction.delta }}
          </span>
        </div>
      </div>
    </section>

    <ChildNav />

    <TaskSubmitModal
      v-model:show="showSubmit"
      :task="activeTask"
      :busy="submitting"
      @submit="submit"
    />
  </main>

  <main v-else class="child-shell">
    <EmptyState
      emoji="🫙"
      title="心愿罐暂时打不开"
      :text="error || '请稍后刷新页面再试一次。'"
    />
  </main>
</template>
