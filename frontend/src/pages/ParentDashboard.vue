<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  NButton,
  NInput,
  NModal,
  NSpin,
  useDialog,
  useMessage,
} from 'naive-ui'
import { api } from '../api'
import EmptyState from '../components/EmptyState.vue'
import ParentNav from '../components/ParentNav.vue'
import TaskSubmitModal from '../components/TaskSubmitModal.vue'
import type {
  ParentDashboard,
  Redemption,
  SavingsLock,
  Submission,
  TodayTask,
} from '../types'
import {
  formatDate,
  formatDateTime,
  lockStatusLabel,
  taskTypeLabel,
} from '../utils'

const dialog = useDialog()
const message = useMessage()

const dashboard = ref<ParentDashboard | null>(null)
const loading = ref(true)
const error = ref('')

const reviewOpen = ref(false)
const reviewKind = ref<'submission' | 'redemption'>('submission')
const reviewTarget = ref<Submission | Redemption | null>(null)
const reviewApprove = ref(true)
const reviewNote = ref('')
const reviewBusy = ref(false)

const quickOpen = ref(false)
const quickTask = ref<TodayTask | null>(null)
const quickBusy = ref(false)
const quickLoggingId = ref<number | null>(null)

const adjustChildId = ref<number | null>(null)
const adjustDelta = ref<number | null>(null)
const adjustNote = ref('')
const adjusting = ref(false)

const pendingCount = computed(
  () =>
    (dashboard.value?.pending_submissions.length ?? 0) +
    (dashboard.value?.pending_redemptions.length ?? 0),
)

const reviewTitle = computed(() =>
  reviewKind.value === 'submission'
    ? reviewApprove.value
      ? '通过这次任务提交'
      : '驳回这次任务提交'
    : reviewApprove.value
      ? '通过这次兑换申请'
      : '驳回这次兑换申请',
)

async function load() {
  loading.value = true
  error.value = ''
  try {
    dashboard.value = await api.parentDashboard()
    if (
      !adjustChildId.value ||
      !dashboard.value.children.some(
        (child) => child.member.id === adjustChildId.value,
      )
    ) {
      adjustChildId.value = dashboard.value.children[0]?.member.id ?? null
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : '家长台暂时打不开'
  } finally {
    loading.value = false
  }
}

onMounted(load)

function openReview(
  kind: 'submission' | 'redemption',
  target: Submission | Redemption,
  approve: boolean,
) {
  reviewKind.value = kind
  reviewTarget.value = target
  reviewApprove.value = approve
  reviewNote.value = ''
  reviewOpen.value = true
}

function targetTitle(target: Submission | Redemption | null) {
  if (!target) return ''
  if ('task_title' in target) return target.task_title
  return `${target.reward_emoji} ${target.reward_title}`
}

async function submitReview() {
  const target = reviewTarget.value
  if (!target) return
  reviewBusy.value = true
  try {
    if (reviewKind.value === 'submission') {
      await api.reviewSubmission(target.id, {
        approve: reviewApprove.value,
        note: reviewNote.value.trim(),
      })
    } else {
      await api.reviewRedemption(target.id, {
        approve: reviewApprove.value,
        note: reviewNote.value.trim(),
      })
    }
    message.success(reviewApprove.value ? '已通过' : '已驳回')
    reviewOpen.value = false
    await load()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '操作失败，请再试一次')
  } finally {
    reviewBusy.value = false
  }
}

async function quickLog(task: TodayTask) {
  if (task.status === 'done' || task.status === 'pending') return
  if (task.requires_photo) {
    quickTask.value = task
    quickOpen.value = true
    return
  }
  quickLoggingId.value = task.id
  try {
    await api.submitTask(task.id, '家长代记')
    message.success(`已为 ${task.child_name} 记上 ${task.points} 分`)
    await load()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '代记失败，请再试一次')
  } finally {
    quickLoggingId.value = null
  }
}

async function submitQuick(note: string, photo: File | null) {
  if (!quickTask.value) return
  quickBusy.value = true
  try {
    await api.submitTask(quickTask.value.id, note || '家长代记', photo)
    message.success(`已为 ${quickTask.value.child_name} 记上 ${quickTask.value.points} 分`)
    quickOpen.value = false
    await load()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '代记失败，请再试一次')
  } finally {
    quickBusy.value = false
  }
}

function releaseLock(lock: SavingsLock) {
  dialog.warning({
    title: '释放锁定积分？',
    content: `将释放 ${lock.child_name} 为「${lock.reward_title}」锁定的 ${lock.amount} 积分。释放后这些积分会重新变成可用积分。`,
    positiveText: '释放',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await api.releaseSavings(lock.id)
        message.success('锁定积分已释放')
        await load()
      } catch (err) {
        message.error(err instanceof Error ? err.message : '释放失败')
      }
    },
  })
}

async function fulfill(redemption: Redemption) {
  try {
    await api.fulfillRedemption(redemption.id)
    message.success('已标记为线下兑现')
    await load()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '操作失败')
  }
}

function taskStatus(task: TodayTask) {
  if (task.status === 'done') return '已完成'
  if (task.status === 'pending') return '待审核'
  if (task.status === 'rejected') return '可重新提交'
  return '未完成'
}

async function adjustPoints() {
  if (!adjustChildId.value) {
    message.warning('先选择孩子')
    return
  }
  if (!adjustDelta.value) {
    message.warning('请输入要调整的积分，正数增加、负数扣减')
    return
  }
  if (!adjustNote.value.trim()) {
    message.warning('请写一句调整原因')
    return
  }
  adjusting.value = true
  try {
    await api.adjustPoints(
      adjustChildId.value,
      Number(adjustDelta.value),
      adjustNote.value.trim(),
    )
    message.success('积分已调整')
    adjustDelta.value = null
    adjustNote.value = ''
    await load()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '调整失败')
  } finally {
    adjusting.value = false
  }
}
</script>

<template>
  <div v-if="loading" class="loading-state">
    <n-spin size="large" />
  </div>

  <main v-else class="parent-shell page-enter">
    <ParentNav />

    <header class="parent-title">
      <p class="eyebrow">FAMILY DESK</p>
      <h1>{{ dashboard?.family_name || '家庭' }}的家长台</h1>
      <p>
        {{ pendingCount > 0 ? `有 ${pendingCount} 件小事在等你确认。` : '今天暂时没有待审核的事，辛苦了。' }}
      </p>
    </header>

    <div v-if="error">
      <EmptyState emoji="🫙" title="家长台暂时打不开" :text="error" />
    </div>

    <template v-else-if="dashboard">
      <section class="panel">
        <div class="panel-head">
          <div>
            <h2>孩子们</h2>
            <p class="hint">积分、可用余额和本周获得</p>
          </div>
        </div>
        <div v-if="dashboard.children.length === 0">
          <EmptyState
            emoji="🌱"
            title="还没有孩子账号"
            text="去管理页添加一个孩子，开始使用心愿罐。"
          />
        </div>
        <div v-else class="child-summary-grid">
          <article
            v-for="child in dashboard.children"
            :key="child.member.id"
            class="child-summary"
          >
            <div class="face">{{ child.member.avatar }}</div>
            <div>
              <h3>{{ child.member.name }}</h3>
              <p>Lv.{{ child.level }} · 本周 +{{ child.week_earned }}</p>
              <div class="summary-stats">
                <span>余额 <strong>{{ child.balance }}</strong></span>
                <span>可用 <strong>{{ child.available }}</strong></span>
                <span>锁定 <strong>{{ child.locked }}</strong></span>
              </div>
            </div>
          </article>
        </div>
      </section>

      <div class="parent-grid" style="margin-top: 18px">
        <div>
          <section class="panel">
            <div class="panel-head">
              <div>
                <h2>待审核提交</h2>
                <p class="hint">孩子完成的任务</p>
              </div>
              <span class="pill amber">{{ dashboard.pending_submissions.length }}</span>
            </div>
            <div v-if="dashboard.pending_submissions.length === 0">
              <EmptyState emoji="✅" title="没有待审核的提交" />
            </div>
            <div v-else class="review-list">
              <article
                v-for="submission in dashboard.pending_submissions"
                :key="submission.id"
                class="review-card"
              >
                <h3>{{ submission.task_title }}</h3>
                <p>
                  {{ submission.child_name }} ·
                  {{ formatDateTime(submission.submitted_at) }}
                </p>
                <p v-if="submission.note">“{{ submission.note }}”</p>
                <img
                  v-if="submission.photo_url"
                  :src="submission.photo_url"
                  class="review-photo"
                  alt="任务照片"
                />
                <div class="review-actions">
                  <n-button
                    size="small"
                    type="primary"
                    secondary
                    @click="openReview('submission', submission, true)"
                  >
                    通过
                  </n-button>
                  <n-button
                    size="small"
                    tertiary
                    @click="openReview('submission', submission, false)"
                  >
                    驳回
                  </n-button>
                </div>
              </article>
            </div>
          </section>

          <section class="panel">
            <div class="panel-head">
              <div>
                <h2>待审核兑换</h2>
                <p class="hint">通过时会扣积分和库存</p>
              </div>
              <span class="pill teal">{{ dashboard.pending_redemptions.length }}</span>
            </div>
            <div v-if="dashboard.pending_redemptions.length === 0">
              <EmptyState emoji="🎁" title="没有待审核的兑换" />
            </div>
            <div v-else class="review-list">
              <article
                v-for="redemption in dashboard.pending_redemptions"
                :key="redemption.id"
                class="review-card redemption"
              >
                <h3>{{ redemption.reward_emoji }} {{ redemption.reward_title }}</h3>
                <p>
                  {{ redemption.child_name }} · {{ redemption.cost_points }} 积分 ·
                  {{ formatDateTime(redemption.requested_at) }}
                </p>
                <div class="review-actions">
                  <n-button
                    size="small"
                    type="primary"
                    secondary
                    @click="openReview('redemption', redemption, true)"
                  >
                    通过
                  </n-button>
                  <n-button
                    size="small"
                    tertiary
                    @click="openReview('redemption', redemption, false)"
                  >
                    驳回
                  </n-button>
                </div>
              </article>
            </div>
          </section>

          <section class="panel">
            <div class="panel-head">
              <div>
                <h2>待线下兑现</h2>
                <p class="hint">已经扣分，等待把奖励给孩子</p>
              </div>
              <span class="pill">{{ dashboard.unfulfilled_redemptions.length }}</span>
            </div>
            <div v-if="dashboard.unfulfilled_redemptions.length === 0">
              <EmptyState emoji="📦" title="没有待兑现的奖励" />
            </div>
            <div v-else class="review-list">
              <article
                v-for="redemption in dashboard.unfulfilled_redemptions"
                :key="redemption.id"
                class="review-card redemption"
              >
                <h3>{{ redemption.reward_emoji }} {{ redemption.reward_title }}</h3>
                <p>{{ redemption.child_name }} · {{ redemption.cost_points }} 积分</p>
                <div class="review-actions">
                  <n-button size="small" type="primary" @click="fulfill(redemption)">
                    标记已兑现
                  </n-button>
                </div>
              </article>
            </div>
          </section>
        </div>

        <div>
          <section class="panel">
            <div class="panel-head">
              <div>
                <h2>今日任务 · 快速代记</h2>
                <p class="hint">点一下就能记分，家长代记立即通过</p>
              </div>
            </div>
            <div v-if="dashboard.today_tasks.length === 0">
              <EmptyState emoji="🌤️" title="今天没有安排任务" />
            </div>
            <div v-else class="quick-grid">
              <div
                v-for="task in dashboard.today_tasks"
                :key="task.id"
                class="quick-card"
              >
                <div>
                  <strong>{{ task.title }}</strong>
                  <span>
                    {{ task.child_name }} · +{{ task.points }} ·
                    {{ taskTypeLabel(task.task_type) }} · {{ taskStatus(task) }}
                  </span>
                </div>
                <n-button
                  v-if="task.status === 'todo' || task.status === 'rejected'"
                  size="small"
                  type="primary"
                  secondary
                  :loading="quickLoggingId === task.id"
                  @click="quickLog(task)"
                >
                  代记
                </n-button>
                <span v-else class="pill" :class="task.status === 'done' ? 'teal' : 'amber'">
                  {{ taskStatus(task) }}
                </span>
              </div>
            </div>
          </section>

          <section class="panel">
            <div class="panel-head">
              <div>
                <h2>心愿锁定</h2>
                <p class="hint">只有家长可以释放</p>
              </div>
              <span class="pill teal">{{ dashboard.active_locks.length }}</span>
            </div>
            <div v-if="dashboard.active_locks.length === 0">
              <EmptyState emoji="🔒" title="还没有锁定储蓄" />
            </div>
            <div v-else class="review-list">
              <article
                v-for="lock in dashboard.active_locks"
                :key="lock.id"
                class="review-card redemption"
              >
                <h3>{{ lock.reward_title }}</h3>
                <p>
                  {{ lock.child_name }} · 锁定 {{ lock.amount }} 积分 ·
                  {{ formatDate(lock.created_at) }}
                </p>
                <p class="muted" style="font-size: 11px">
                  {{ lockStatusLabel(lock.status) }} · {{ lock.note || '为长期心愿储蓄' }}
                </p>
                <div class="review-actions">
                  <n-button size="small" tertiary @click="releaseLock(lock)">
                    释放锁定
                  </n-button>
                </div>
              </article>
            </div>
          </section>

          <section class="panel">
            <div class="panel-head">
              <div>
                <h2>手动调整积分</h2>
                <p class="hint">备注必填；调整后不能低于已锁定积分</p>
              </div>
            </div>
            <div v-if="dashboard.children.length === 0">
              <EmptyState emoji="🌱" title="还没有孩子账号" />
            </div>
            <div v-else class="modal-form">
              <div class="field">
                <label>孩子</label>
                <select v-model="adjustChildId" class="native-input">
                  <option
                    v-for="child in dashboard.children"
                    :key="child.member.id"
                    :value="child.member.id"
                  >
                    {{ child.member.avatar }} {{ child.member.name }}
                  </option>
                </select>
              </div>
              <div class="field">
                <label>调整积分（正数增加，负数扣减）</label>
                <input
                  v-model.number="adjustDelta"
                  type="number"
                  class="native-input"
                  placeholder="例如：10 或 -5"
                />
              </div>
              <div class="field">
                <label>备注</label>
                <n-input
                  v-model:value="adjustNote"
                  maxlength="200"
                  placeholder="例如：主动帮忙做家务"
                />
              </div>
              <n-button type="primary" :loading="adjusting" @click="adjustPoints">
                确认调整
              </n-button>
            </div>
          </section>
        </div>
      </div>
    </template>

    <TaskSubmitModal
      v-model:show="quickOpen"
      :task="quickTask"
      :busy="quickBusy"
      @submit="submitQuick"
    />

    <n-modal
      v-model:show="reviewOpen"
      preset="card"
      :style="{ width: 'min(500px, 92vw)' }"
      :title="reviewTitle"
      :mask-closable="!reviewBusy"
    >
      <div class="modal-form">
        <p class="muted" style="font-size: 13px">
          {{ targetTitle(reviewTarget) }}
        </p>
        <div class="field">
          <label>评语（可选）</label>
          <n-input
            v-model:value="reviewNote"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 4 }"
            maxlength="500"
            show-count
            placeholder="例如：读得很认真，继续保持"
          />
        </div>
      </div>
      <template #footer>
        <div class="modal-footer">
          <n-button :disabled="reviewBusy" @click="reviewOpen = false">
            取消
          </n-button>
          <n-button
            :type="reviewApprove ? 'primary' : 'error'"
            :loading="reviewBusy"
            @click="submitReview"
          >
            {{ reviewApprove ? '确认通过' : '确认驳回' }}
          </n-button>
        </div>
      </template>
    </n-modal>
  </main>
</template>
