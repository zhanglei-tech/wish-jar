<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { NButton, NInput, NSpin, useMessage } from 'naive-ui'
import { api } from '../api'
import ChildNav from '../components/ChildNav.vue'
import EmptyState from '../components/EmptyState.vue'
import type { Wish } from '../types'
import { emojiChoices, formatDateTime } from '../utils'

const message = useMessage()
const wishes = ref<Wish[]>([])
const loading = ref(true)
const error = ref('')
const submitting = ref(false)
const showForm = ref(false)
const imageFile = ref<File | null>(null)
const imagePreview = ref<string | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

const form = reactive({
  title: '',
  emoji: '⭐',
  reason: '',
  expected_points: 100,
})

const statusText: Record<string, string> = {
  pending: '等家长看看',
  listed: '已经上架',
  rejected: '这次没有上架',
}

function statusClass(status: string) {
  if (status === 'listed') return 'teal'
  if (status === 'rejected') return 'accent'
  return 'amber'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    wishes.value = await api.wishes()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '心愿暂时打不开'
  } finally {
    loading.value = false
  }
}

onMounted(load)

function setImage(file: File | null) {
  if (imagePreview.value) {
    URL.revokeObjectURL(imagePreview.value)
  }
  imageFile.value = file
  imagePreview.value = file ? URL.createObjectURL(file) : null
}

function pickImage(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0] ?? null
  if (!file) return
  if (file.size > 2 * 1024 * 1024) {
    message.warning('图片不能超过 2MB')
    target.value = ''
    return
  }
  setImage(file)
}

function resetImage() {
  setImage(null)
  if (fileInput.value) fileInput.value.value = ''
}

onBeforeUnmount(() => {
  if (imagePreview.value) {
    URL.revokeObjectURL(imagePreview.value)
  }
})

async function submitWish() {
  if (!form.title.trim()) {
    message.warning('先给心愿起个名字')
    return
  }
  submitting.value = true
  try {
    await api.createWish({
      title: form.title.trim(),
      emoji: form.emoji,
      reason: form.reason.trim(),
      expected_points: Number(form.expected_points) || 0,
      image: imageFile.value,
    })
    message.success('心愿已经放进罐子里，等家长看看')
    form.title = ''
    form.reason = ''
    form.expected_points = 100
    form.emoji = '⭐'
    resetImage()
    showForm.value = false
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

  <main v-else class="child-shell page-enter">
    <header class="child-header">
      <div>
        <p class="eyebrow">MAKE A WISH</p>
        <h1 class="display-title">我的心愿</h1>
        <p class="muted">把想要的事情告诉家长，说不定就会出现在心愿商店里。</p>
      </div>
      <router-link to="/me" class="avatar-button" aria-label="我的">🌱</router-link>
    </header>

    <div class="section-heading">
      <h2>许一个愿</h2>
      <n-button type="primary" secondary @click="showForm = !showForm">
        {{ showForm ? '收起' : '写下心愿' }}
      </n-button>
    </div>

    <section v-if="showForm" class="detail-card">
      <div class="modal-form">
        <div class="field">
          <label>心愿名字</label>
          <n-input v-model:value="form.title" maxlength="100" placeholder="例如：一套乐高" />
        </div>
        <div class="field">
          <label>挑一个图标</label>
          <div class="emoji-picker">
            <button
              v-for="emoji in emojiChoices"
              :key="emoji"
              type="button"
              class="emoji-chip"
              :class="{ active: form.emoji === emoji }"
              :aria-label="`选择图标 ${emoji}`"
              :aria-pressed="form.emoji === emoji"
              @click="form.emoji = emoji"
            >
              {{ emoji }}
            </button>
          </div>
        </div>
        <div class="field">
          <label>为什么想要它</label>
          <n-input
            v-model:value="form.reason"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 4 }"
            maxlength="500"
            placeholder="说一说你的想法，家长定价时会更了解。"
          />
        </div>
        <div class="field">
          <label>期望积分（仅供参考）</label>
          <input
            v-model.number="form.expected_points"
            type="number"
            min="0"
            class="native-input"
          />
        </div>
        <div class="field">
          <label>图片（可选，≤2MB）</label>
          <div class="wish-image-row">
            <img v-if="imagePreview" :src="imagePreview" class="wish-preview" alt="心愿图片预览" />
            <label class="file-button">
              {{ imageFile ? '更换图片' : '选择图片' }}
              <input
                ref="fileInput"
                type="file"
                accept="image/jpeg,image/png,image/webp"
                @change="pickImage"
              />
            </label>
            <button v-if="imageFile" type="button" class="link-button" @click="resetImage">
              移除
            </button>
          </div>
          <span v-if="imageFile" class="wish-file-name">{{ imageFile.name }}</span>
        </div>
        <n-button type="primary" size="large" :loading="submitting" @click="submitWish">
          放进心愿罐
        </n-button>
      </div>
    </section>

    <div v-if="error">
      <EmptyState emoji="🫙" title="心愿暂时打不开" :text="error" />
    </div>
    <div v-else-if="wishes.length === 0" class="section">
      <EmptyState
        emoji="🌟"
        title="还没有许过愿"
        text="写下一个想要的东西，让家长帮你把它变成可以努力的方向。"
      />
    </div>
    <div v-else class="task-list section">
      <article v-for="wish in wishes" :key="wish.id" class="goal-card">
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
          <span class="pill" :class="statusClass(wish.status)">
            {{ statusText[wish.status] }}
          </span>
        </div>
        <p v-if="wish.reason" class="muted" style="font-size: 13px">
          “{{ wish.reason }}”
        </p>
        <div class="wish-meta">
          <span class="pill">期望 {{ wish.expected_points }} 积分</span>
          <span class="muted" style="font-size: 11px">
            {{ formatDateTime(wish.created_at) }}
          </span>
        </div>
        <p v-if="wish.status === 'listed' && wish.reward_title" class="muted" style="font-size: 12px">
          已经变成奖励「{{ wish.reward_title }}」，可以去心愿商店看看。
        </p>
        <p v-if="wish.status === 'rejected'" class="muted" style="font-size: 12px">
          家长说：{{ wish.reject_reason || '这次先不放进商店。' }}
        </p>
      </article>
    </div>

    <ChildNav />
  </main>
</template>
