<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { NButton, NInput, NModal, NSpin, NSwitch, useMessage } from 'naive-ui'
import { api } from '../api'
import EmptyState from '../components/EmptyState.vue'
import ParentNav from '../components/ParentNav.vue'
import type { RewardUnit, Wish } from '../types'
import { formatDateTime } from '../utils'

const message = useMessage()
const wishes = ref<Wish[]>([])
const loading = ref(true)
const error = ref('')
const statusFilter = ref<'pending' | 'all'>('pending')

const listOpen = ref(false)
const activeWish = ref<Wish | null>(null)
const saving = ref(false)
const listForm = reactive({
  title: '',
  emoji: '🎁',
  description: '',
  value: 100,
  unit: 'points' as RewardUnit,
  multiplier: 1,
  stock: 1,
  is_long_term: false,
  auto_match_percent: 0,
})

const rejectOpen = ref(false)
const rejectReason = ref('')

const unitOptions: { label: string; value: RewardUnit }[] = [
  { label: '积分', value: 'points' },
  { label: '元', value: 'yuan' },
  { label: '分钟', value: 'minutes' },
  { label: '次', value: 'times' },
]

const costPreview = computed(() =>
  Math.max(0, Math.ceil((Number(listForm.value) || 0) * (Number(listForm.multiplier) || 0))),
)

async function load() {
  loading.value = true
  error.value = ''
  try {
    wishes.value = await api.wishes(
      statusFilter.value === 'pending' ? 'pending' : undefined,
    )
  } catch (err) {
    error.value = err instanceof Error ? err.message : '心愿列表暂时打不开'
  } finally {
    loading.value = false
  }
}

onMounted(load)

function openList(wish: Wish) {
  activeWish.value = wish
  Object.assign(listForm, {
    title: wish.title,
    emoji: wish.emoji || '🎁',
    description: wish.reason,
    value: wish.expected_points || 100,
    unit: 'points',
    multiplier: 1,
    stock: 1,
    is_long_term: false,
    auto_match_percent: 0,
  })
  listOpen.value = true
}

async function saveList() {
  if (!activeWish.value) return
  saving.value = true
  try {
    await api.listWish(activeWish.value.id, {
      title: listForm.title.trim() || undefined,
      emoji: listForm.emoji,
      description: listForm.description,
      value: Number(listForm.value) || 0,
      unit: listForm.unit,
      multiplier: Number(listForm.multiplier) || 1,
      stock: Number(listForm.stock),
      is_long_term: listForm.is_long_term,
      auto_match_percent: Number(listForm.auto_match_percent) || 0,
    })
    message.success('心愿已上架到奖励商店')
    listOpen.value = false
    await load()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '上架失败')
  } finally {
    saving.value = false
  }
}

function openReject(wish: Wish) {
  activeWish.value = wish
  rejectReason.value = ''
  rejectOpen.value = true
}

async function saveReject() {
  if (!activeWish.value) return
  if (!rejectReason.value.trim()) {
    message.warning('写一句原因，孩子会更明白')
    return
  }
  saving.value = true
  try {
    await api.rejectWish(activeWish.value.id, rejectReason.value.trim())
    message.success('已驳回并留下原因')
    rejectOpen.value = false
    await load()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '驳回失败')
  } finally {
    saving.value = false
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
      <p class="eyebrow">WISH MAILBOX</p>
      <h1>孩子的心愿</h1>
      <p>孩子写下的愿望，可以定价上架，也可以留一句解释。</p>
    </header>

    <div class="stats-toolbar">
      <div class="period-tabs">
        <button
          type="button"
          :class="{ active: statusFilter === 'pending' }"
          @click="statusFilter = 'pending'; load()"
        >
          待处理
        </button>
        <button
          type="button"
          :class="{ active: statusFilter === 'all' }"
          @click="statusFilter = 'all'; load()"
        >
          全部
        </button>
      </div>
    </div>

    <div v-if="error">
      <EmptyState emoji="🫙" title="心愿列表暂时打不开" :text="error" />
    </div>
    <div v-else-if="wishes.length === 0" class="panel">
      <EmptyState
        emoji="💌"
        title="没有待处理的心愿"
        :text="statusFilter === 'pending' ? '孩子提交心愿后会出现在这里。' : '还没有孩子许过愿。'"
      />
    </div>
    <div v-else class="wish-review-list">
      <article v-for="wish in wishes" :key="wish.id" class="panel wish-review-card">
        <div class="goal-top">
          <div class="goal-title">
            <img
              v-if="wish.image_url"
              :src="wish.image_url"
              class="wish-thumb"
              alt="心愿图片"
            />
            <span v-else class="emoji">{{ wish.emoji }}</span>
            {{ wish.title }}
          </div>
          <span
            class="pill"
            :class="wish.status === 'listed' ? 'teal' : wish.status === 'rejected' ? 'accent' : 'amber'"
          >
            {{ wish.status === 'pending' ? '待定价' : wish.status === 'listed' ? '已上架' : '已驳回' }}
          </span>
        </div>
        <p class="muted" style="font-size: 13px">
          {{ wish.child_name }} · 期望 {{ wish.expected_points }} 积分 ·
          {{ formatDateTime(wish.created_at) }}
        </p>
        <p v-if="wish.reason" style="font-size: 14px">“{{ wish.reason }}”</p>
        <p v-if="wish.reward_title" class="muted" style="font-size: 12px">
          对应奖励：{{ wish.reward_title }}
        </p>
        <p v-if="wish.reject_reason" class="muted" style="font-size: 12px">
          驳回原因：{{ wish.reject_reason }}
        </p>
        <div v-if="wish.status === 'pending'" class="review-actions">
          <n-button size="small" type="primary" @click="openList(wish)">定价上架</n-button>
          <n-button size="small" tertiary @click="openReject(wish)">驳回</n-button>
        </div>
      </article>
    </div>

    <n-modal
      v-model:show="listOpen"
      preset="card"
      title="把心愿上架"
      :style="{ width: 'min(560px, 92vw)' }"
    >
      <div class="modal-form">
        <div class="field-row">
          <div class="field">
            <label>奖励名字</label>
            <n-input v-model:value="listForm.title" maxlength="100" />
          </div>
          <div class="field">
            <label>图标</label>
            <n-input v-model:value="listForm.emoji" maxlength="16" />
          </div>
        </div>
        <div class="field">
          <label>说明</label>
          <n-input
            v-model:value="listForm.description"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 3 }"
          />
        </div>
        <div class="field-row three">
          <div class="field">
            <label>标价</label>
            <input v-model.number="listForm.value" type="number" min="0" class="native-input" />
          </div>
          <div class="field">
            <label>单位</label>
            <select v-model="listForm.unit" class="native-input">
              <option v-for="option in unitOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </div>
          <div class="field">
            <label>倍率</label>
            <input
              v-model.number="listForm.multiplier"
              type="number"
              min="0.1"
              step="0.1"
              class="native-input"
            />
          </div>
        </div>
        <div class="field-row three">
          <div class="field">
            <label>库存（-1 不限）</label>
            <input v-model.number="listForm.stock" type="number" min="-1" class="native-input" />
          </div>
          <div class="field">
            <label>所需积分</label>
            <input :value="costPreview" class="native-input" disabled />
          </div>
          <div class="field">
            <label>自动配捐 %（长期心愿）</label>
            <input
              v-model.number="listForm.auto_match_percent"
              type="number"
              min="0"
              max="100"
              class="native-input"
            />
          </div>
        </div>
        <div class="check-row">
          <div>
            <strong>长期心愿</strong>
            <span>支持锁定储蓄、家长配捐和进度展示</span>
          </div>
          <n-switch v-model:value="listForm.is_long_term" />
        </div>
      </div>
      <template #footer>
        <div class="modal-footer">
          <n-button @click="listOpen = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="saveList">上架</n-button>
        </div>
      </template>
    </n-modal>

    <n-modal
      v-model:show="rejectOpen"
      preset="card"
      title="驳回这个心愿"
      :style="{ width: 'min(480px, 92vw)' }"
    >
      <div class="modal-form">
        <div class="field">
          <label>原因</label>
          <n-input
            v-model:value="rejectReason"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 4 }"
            maxlength="300"
            placeholder="例如：这个愿望太贵了，我们换一个小一点的？"
          />
        </div>
      </div>
      <template #footer>
        <div class="modal-footer">
          <n-button @click="rejectOpen = false">取消</n-button>
          <n-button type="error" :loading="saving" @click="saveReject">确认驳回</n-button>
        </div>
      </template>
    </n-modal>
  </main>
</template>
