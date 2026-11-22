<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NButton, NSpin } from 'naive-ui'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'
import type { MemberPublic } from '../types'

const router = useRouter()
const auth = useAuthStore()

const members = ref<MemberPublic[]>([])
const selectedId = ref<number | null>(null)
const pin = ref('')
const loading = ref(true)
const submitting = ref(false)
const error = ref('')

const selected = computed(
  () => members.value.find((member) => member.id === selectedId.value) ?? null,
)

onMounted(async () => {
  try {
    members.value = await api.authMembers()
    if (members.value.length === 0) {
      await router.replace('/setup')
      return
    }
    selectedId.value =
      members.value.find((member) => member.role === 'parent')?.id ??
      members.value[0]?.id ??
      null
  } catch {
    error.value = '暂时无法读取家庭成员，请稍后再试'
  } finally {
    loading.value = false
  }
})

function choose(member: MemberPublic) {
  selectedId.value = member.id
  pin.value = ''
  error.value = ''
}

function append(digit: string) {
  if (pin.value.length >= 4) return
  pin.value += digit
}

function backspace() {
  pin.value = pin.value.slice(0, -1)
}

function clearPin() {
  pin.value = ''
}

async function submit() {
  if (!selected.value) {
    error.value = '先选择你是谁'
    return
  }
  if (pin.value.length !== 4) {
    error.value = '请输入 4 位数字 PIN'
    return
  }
  submitting.value = true
  error.value = ''
  try {
    await auth.login(selected.value.id, pin.value)
    await router.replace(selected.value.role === 'parent' ? '/parent' : '/')
  } catch (err) {
    pin.value = ''
    error.value = err instanceof Error ? err.message : '登录失败，请再试一次'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <main class="login-shell page-enter">
    <section class="login-card">
      <div class="brand-seal" style="margin: 0 auto 10px">
        <span class="seal">愿</span>
        心愿罐
      </div>
      <h1>今天想存点什么？</h1>
      <p class="muted">选择你的名字，输入 PIN 进入。</p>

      <div v-if="loading" style="padding: 30px 0">
        <n-spin size="large" />
      </div>

      <template v-else>
        <div class="member-picker">
          <button
            v-for="member in members"
            :key="member.id"
            type="button"
            class="member-choice"
            :class="{ selected: member.id === selectedId }"
            @click="choose(member)"
          >
            <span class="face">{{ member.avatar }}</span>
            <strong>{{ member.name }}</strong>
            <span>{{ member.role === 'parent' ? '家长' : '孩子' }}</span>
          </button>
        </div>

        <div class="pin-dots" aria-label="PIN 输入">
          <span
            v-for="index in 4"
            :key="index"
            class="pin-dot"
            :class="{ filled: pin.length >= index }"
          />
        </div>

        <div class="pin-keypad">
          <button
            v-for="digit in ['1', '2', '3', '4', '5', '6', '7', '8', '9']"
            :key="digit"
            type="button"
            class="key"
            @click="append(digit)"
          >
            {{ digit }}
          </button>
          <button type="button" class="key subtle" @click="clearPin">清空</button>
          <button type="button" class="key" @click="append('0')">0</button>
          <button type="button" class="key subtle" @click="backspace">⌫</button>
        </div>

        <p class="login-error">{{ error }}</p>

        <n-button
          type="primary"
          size="large"
          block
          :loading="submitting"
          :disabled="!selected"
          @click="submit"
        >
          进入心愿罐
        </n-button>
      </template>
    </section>
  </main>
</template>
