<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { NButton, NInput, NSelect, NSpin, NSwitch, useMessage } from 'naive-ui'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'
import { emojiChoices } from '../utils'

const router = useRouter()
const auth = useAuthStore()
const message = useMessage()

const checking = ref(true)
const saving = ref(false)
const form = reactive({
  family_name: '',
  parent_name: '',
  parent_avatar: '🦉',
  parent_pin: '',
  child_enabled: true,
  child_name: '',
  child_avatar: '🌱',
  child_pin: '',
  approval_required: true,
  create_samples: true,
})

const avatarOptions = emojiChoices.map((emoji) => ({ label: emoji, value: emoji }))

onMounted(async () => {
  try {
    const status = await api.setupStatus()
    if (!status.needs_setup) {
      await router.replace(auth.member?.role === 'parent' ? '/parent' : '/login')
      return
    }
  } catch {
    message.error('暂时无法连接心愿罐，请稍后再试')
  } finally {
    checking.value = false
  }
})

function validPin(pin: string) {
  return /^\d{4}$/.test(pin)
}

async function submit() {
  if (!form.family_name.trim()) {
    message.warning('给家庭起一个名字吧')
    return
  }
  if (!form.parent_name.trim() || !validPin(form.parent_pin)) {
    message.warning('请填写家长名字和 4 位数字 PIN')
    return
  }
  if (form.child_enabled && (!form.child_name.trim() || !validPin(form.child_pin))) {
    message.warning('请填写孩子名字和 4 位数字 PIN')
    return
  }
  saving.value = true
  try {
    const result = await api.setup({
      family_name: form.family_name.trim(),
      parent: {
        name: form.parent_name.trim(),
        avatar: form.parent_avatar,
        pin: form.parent_pin,
      },
      child: form.child_enabled
        ? {
            name: form.child_name.trim(),
            avatar: form.child_avatar,
            pin: form.child_pin,
            approval_required: form.approval_required,
          }
        : undefined,
      create_samples: form.create_samples,
    })
    auth.setSession(result)
    auth.needsSetup = false
    auth.checked = true
    message.success('心愿罐已经准备好了')
    await router.replace('/parent')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '初始化失败，请稍后再试')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div v-if="checking" class="loading-state">
    <n-spin size="large" />
  </div>

  <main v-else class="setup-shell page-enter">
    <section class="setup-story">
      <div class="brand-seal">
        <span class="seal">愿</span>
        心愿罐 · WISH JAR
      </div>
      <h1>把每一份努力，<br /><em>慢慢存成心愿。</em></h1>
      <p class="lead">
        给孩子一个看得见的成长罐。完成每天的小任务，积累积分，靠近自己认真许下的愿望。
      </p>
      <div class="story-notes">
        <span>每天一点小进步</span>
        <span>长期心愿锁定储蓄</span>
        <span>家长代记更轻松</span>
        <span>数据只留在家里</span>
      </div>
    </section>

    <section class="setup-form-card">
      <div class="form-heading">
        <h2>第一次打开</h2>
        <p>花一分钟，建好这个家的心愿罐。</p>
      </div>

      <div class="field">
        <label>家庭名字</label>
        <n-input
          v-model:value="form.family_name"
          maxlength="100"
          placeholder="例如：小满一家"
        />
      </div>

      <div class="field-row">
        <div class="field">
          <label>家长名字</label>
          <n-input
            v-model:value="form.parent_name"
            maxlength="50"
            placeholder="例如：妈妈"
          />
        </div>
        <div class="field">
          <label>头像</label>
          <n-select v-model:value="form.parent_avatar" :options="avatarOptions" />
        </div>
      </div>

      <div class="field">
        <label>家长 PIN（4 位数字）</label>
        <n-input
          v-model:value="form.parent_pin"
          type="password"
          maxlength="4"
          placeholder="例如：1234"
        />
      </div>

      <div class="check-row">
        <div>
          <strong>现在就创建孩子账号</strong>
          <span>之后也可以在管理页里再添加</span>
        </div>
        <n-switch v-model:value="form.child_enabled" />
      </div>

      <template v-if="form.child_enabled">
        <div class="field-row">
          <div class="field">
            <label>孩子名字</label>
            <n-input
              v-model:value="form.child_name"
              maxlength="50"
              placeholder="例如：小满"
            />
          </div>
          <div class="field">
            <label>头像</label>
            <n-select
              v-model:value="form.child_avatar"
              :options="avatarOptions"
            />
          </div>
        </div>

        <div class="field">
          <label>孩子 PIN（4 位数字）</label>
          <n-input
            v-model:value="form.child_pin"
            type="password"
            maxlength="4"
            placeholder="孩子自己记得住的 4 位数字"
          />
        </div>

        <div class="check-row">
          <div>
            <strong>孩子提交任务后需要家长审核</strong>
            <span>家长代记始终立即通过</span>
          </div>
          <n-switch v-model:value="form.approval_required" />
        </div>
      </template>

      <div class="check-row">
        <div>
          <strong>放几个示例目标和奖励</strong>
          <span>可以随时在管理页修改或停用</span>
        </div>
        <n-switch v-model:value="form.create_samples" />
      </div>

      <div class="form-actions">
        <n-button
          type="primary"
          size="large"
          :loading="saving"
          @click="submit"
        >
          开始使用
        </n-button>
      </div>
    </section>
  </main>
</template>
