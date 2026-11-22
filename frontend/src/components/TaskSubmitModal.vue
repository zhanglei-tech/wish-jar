<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { NButton, NInput, NModal } from 'naive-ui'
import type { TodayTask } from '../types'

const props = withDefaults(
  defineProps<{
    show: boolean
    task: TodayTask | null
    busy?: boolean
  }>(),
  {
    busy: false,
  },
)

const emit = defineEmits<{
  'update:show': [value: boolean]
  submit: [note: string, photo: File | null]
}>()

const note = ref('')
const photo = ref<File | null>(null)
const photoName = ref('')
const fileError = ref('')
const fileInput = ref<HTMLInputElement | null>(null)

const canSubmit = computed(
  () => !props.busy && (!props.task?.requires_photo || photo.value !== null),
)

watch(
  () => props.show,
  (visible) => {
    if (visible) {
      note.value = ''
      photo.value = null
      photoName.value = ''
      fileError.value = ''
    }
  },
)

function handleShow(value: boolean) {
  if (!value && !props.busy) emit('update:show', false)
}

function choosePhoto() {
  fileInput.value?.click()
}

function onFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0] ?? null
  fileError.value = ''
  if (!file) {
    photo.value = null
    photoName.value = ''
    return
  }
  const allowed = ['image/jpeg', 'image/png', 'image/webp']
  if (!allowed.includes(file.type)) {
    fileError.value = '请选择 JPG、PNG 或 WebP 照片'
    photo.value = null
    photoName.value = ''
    return
  }
  if (file.size > 5 * 1024 * 1024) {
    fileError.value = '照片不能超过 5MB'
    photo.value = null
    photoName.value = ''
    return
  }
  photo.value = file
  photoName.value = file.name
}

function submit() {
  if (!canSubmit.value) return
  emit('submit', note.value.trim(), photo.value)
}
</script>

<template>
  <n-modal
    :show="props.show"
    preset="card"
    :style="{ width: 'min(520px, 92vw)' }"
    :mask-closable="!props.busy"
    :closable="!props.busy"
    @update:show="handleShow"
  >
    <div class="modal-form">
      <div class="form-heading">
        <h2>{{ props.task?.title || '记录完成' }}</h2>
        <p v-if="props.task">
          完成后可获得
          <strong>+{{ props.task.points }} 积分</strong>
          <span v-if="props.task.requires_photo"> · 需要一张照片凭证</span>
        </p>
      </div>

      <div class="field">
        <label>想说的话（可选）</label>
        <n-input
          v-model:value="note"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 4 }"
          maxlength="500"
          show-count
          placeholder="例如：今天读了 25 分钟，讲了一个很有趣的故事"
        />
      </div>

      <div v-if="props.task?.requires_photo" class="field">
        <label>照片凭证</label>
        <input
          ref="fileInput"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          style="display: none"
          @change="onFileChange"
        />
        <n-button secondary type="primary" @click="choosePhoto">
          {{ photo ? '换一张照片' : '选择照片' }}
        </n-button>
        <span class="muted" style="font-size: 12px">
          {{ photoName || 'JPG / PNG / WebP，不超过 5MB' }}
        </span>
        <span v-if="fileError" class="login-error">{{ fileError }}</span>
      </div>
    </div>

    <template #footer>
      <div class="modal-footer">
        <n-button :disabled="props.busy" @click="emit('update:show', false)">
          取消
        </n-button>
        <n-button
          type="primary"
          :loading="props.busy"
          :disabled="!canSubmit"
          @click="submit"
        >
          提交完成
        </n-button>
      </div>
    </template>
  </n-modal>
</template>
