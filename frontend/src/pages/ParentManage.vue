<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NInput,
  NModal,
  NSpin,
  NSwitch,
  useDialog,
  useMessage,
} from 'naive-ui'
import { api } from '../api'
import EmptyState from '../components/EmptyState.vue'
import ParentNav from '../components/ParentNav.vue'
import type {
  Goal,
  GoalPayload,
  MemberOut,
  MemberPayload,
  Reward,
  RewardPayload,
  RewardUnit,
  Role,
  Task,
  TaskPayload,
  TaskType,
} from '../types'
import { emojiChoices, taskTypeLabel } from '../utils'

type Tab = 'members' | 'goals' | 'tasks' | 'rewards'

const dialog = useDialog()
const message = useMessage()

const activeTab = ref<Tab>('members')
const loading = ref(true)
const error = ref('')
const selectedChildId = ref<number | null>(null)

const members = ref<MemberOut[]>([])
const goals = ref<Goal[]>([])
const tasks = ref<Task[]>([])
const rewards = ref<Reward[]>([])

const children = computed(() =>
  members.value.filter((member) => member.role === 'child'),
)
const childOptions = computed(() =>
  children.value.map((child) => ({
    label: `${child.avatar} ${child.name}`,
    value: child.id,
  })),
)
const filteredGoals = computed(() =>
  selectedChildId.value === null
    ? goals.value
    : goals.value.filter((goal) => goal.child_id === selectedChildId.value),
)
const filteredTasks = computed(() =>
  selectedChildId.value === null
    ? tasks.value
    : tasks.value.filter((task) => task.child_id === selectedChildId.value),
)

const roleOptions: { label: string; value: Role }[] = [
  { label: '家长', value: 'parent' },
  { label: '孩子', value: 'child' },
]
const taskTypeOptions: { label: string; value: TaskType }[] = [
  { label: '每天', value: 'daily' },
  { label: '每周', value: 'weekly' },
  { label: '一次性', value: 'once' },
]
const unitOptions: { label: string; value: RewardUnit }[] = [
  { label: '积分', value: 'points' },
  { label: '元', value: 'yuan' },
  { label: '分钟', value: 'minutes' },
  { label: '次', value: 'times' },
]
const statusOptions = [
  { label: '进行中', value: 'active' },
  { label: '已完成', value: 'completed' },
  { label: '已归档', value: 'archived' },
]

// ---------------------------------------------------------------------------
// Members
// ---------------------------------------------------------------------------

const memberOpen = ref(false)
const editingMember = ref<MemberOut | null>(null)
const memberForm = reactive({
  name: '',
  avatar: '🌱',
  role: 'child' as Role,
  pin: '',
  approval_required: true,
  is_active: true,
})

function openNewMember() {
  editingMember.value = null
  Object.assign(memberForm, {
    name: '',
    avatar: '🌱',
    role: 'child',
    pin: '',
    approval_required: true,
    is_active: true,
  })
  memberOpen.value = true
}

function openEditMember(member: MemberOut) {
  editingMember.value = member
  Object.assign(memberForm, {
    name: member.name,
    avatar: member.avatar,
    role: member.role,
    pin: '',
    approval_required: member.approval_required,
    is_active: member.is_active,
  })
  memberOpen.value = true
}

function validPin(pin: string) {
  return /^\d{4}$/.test(pin)
}

async function saveMember() {
  if (!memberForm.name.trim()) {
    message.warning('成员需要名字')
    return
  }
  if (!editingMember.value && !validPin(memberForm.pin)) {
    message.warning('请设置 4 位数字 PIN')
    return
  }
  if (editingMember.value && memberForm.pin && !validPin(memberForm.pin)) {
    message.warning('PIN 需要是 4 位数字')
    return
  }
  try {
    if (editingMember.value) {
      const payload: Partial<MemberPayload> = {
        name: memberForm.name.trim(),
        avatar: memberForm.avatar,
        approval_required: memberForm.role === 'child' ? memberForm.approval_required : false,
        is_active: memberForm.is_active,
      }
      if (memberForm.pin) payload.pin = memberForm.pin
      await api.updateMember(editingMember.value.id, payload)
    } else {
      await api.createMember({
        name: memberForm.name.trim(),
        avatar: memberForm.avatar,
        role: memberForm.role,
        pin: memberForm.pin,
        approval_required:
          memberForm.role === 'child' ? memberForm.approval_required : false,
      })
    }
    message.success('成员信息已保存')
    memberOpen.value = false
    await load()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '保存失败')
  }
}

// ---------------------------------------------------------------------------
// Goals
// ---------------------------------------------------------------------------

const goalOpen = ref(false)
const editingGoal = ref<Goal | null>(null)
const goalForm = reactive({
  child_id: null as number | null,
  title: '',
  emoji: '🎯',
  description: '',
  target_points: 100,
  start_date: '',
  end_date: '',
  status: 'active' as Goal['status'],
})

function openNewGoal() {
  const child = selectedChildId.value ?? children.value[0]?.id ?? null
  if (!child) {
    message.warning('先添加一个孩子账号')
    return
  }
  editingGoal.value = null
  Object.assign(goalForm, {
    child_id: child,
    title: '',
    emoji: '🎯',
    description: '',
    target_points: 100,
    start_date: '',
    end_date: '',
    status: 'active',
  })
  goalOpen.value = true
}

function openEditGoal(goal: Goal) {
  editingGoal.value = goal
  Object.assign(goalForm, {
    child_id: goal.child_id,
    title: goal.title,
    emoji: goal.emoji,
    description: goal.description,
    target_points: goal.target_points,
    start_date: goal.start_date ?? '',
    end_date: goal.end_date ?? '',
    status: goal.status,
  })
  goalOpen.value = true
}

async function saveGoal() {
  if (!goalForm.child_id || !goalForm.title.trim()) {
    message.warning('请选择孩子并填写目标名字')
    return
  }
  const payload: GoalPayload = {
    child_id: goalForm.child_id,
    title: goalForm.title.trim(),
    emoji: goalForm.emoji,
    description: goalForm.description,
    target_points: Number(goalForm.target_points) || 0,
    start_date: goalForm.start_date || null,
    end_date: goalForm.end_date || null,
  }
  try {
    if (editingGoal.value) {
      await api.updateGoal(editingGoal.value.id, {
        ...payload,
        status: goalForm.status,
      })
    } else {
      await api.createGoal(payload)
    }
    message.success('目标已保存')
    goalOpen.value = false
    await load()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '保存失败')
  }
}

function deleteGoal(goal: Goal) {
  dialog.warning({
    title: '删除这个目标？',
    content: `「${goal.title}」会被删除，关联任务会保留但不再归属于目标。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await api.deleteGoal(goal.id)
        message.success('目标已删除')
        await load()
      } catch (err) {
        message.error(err instanceof Error ? err.message : '删除失败')
      }
    },
  })
}

// ---------------------------------------------------------------------------
// Tasks
// ---------------------------------------------------------------------------

const taskOpen = ref(false)
const editingTask = ref<Task | null>(null)
const taskForm = reactive({
  child_id: null as number | null,
  goal_id: null as number | null,
  title: '',
  description: '',
  points: 20,
  task_type: 'daily' as TaskType,
  requires_photo: false,
  active: true,
})

const taskGoalOptions = computed(() =>
  goals.value
    .filter((goal) => goal.child_id === taskForm.child_id)
    .map((goal) => ({ label: `${goal.emoji} ${goal.title}`, value: goal.id })),
)

function openNewTask() {
  const child = selectedChildId.value ?? children.value[0]?.id ?? null
  if (!child) {
    message.warning('先添加一个孩子账号')
    return
  }
  editingTask.value = null
  Object.assign(taskForm, {
    child_id: child,
    goal_id: null,
    title: '',
    description: '',
    points: 20,
    task_type: 'daily',
    requires_photo: false,
    active: true,
  })
  taskOpen.value = true
}

function openEditTask(task: Task) {
  editingTask.value = task
  Object.assign(taskForm, {
    child_id: task.child_id,
    goal_id: task.goal_id,
    title: task.title,
    description: task.description,
    points: task.points,
    task_type: task.task_type,
    requires_photo: task.requires_photo,
    active: task.active,
  })
  taskOpen.value = true
}

async function saveTask() {
  if (!taskForm.child_id || !taskForm.title.trim()) {
    message.warning('请选择孩子并填写任务名字')
    return
  }
  const base = {
    goal_id: taskForm.goal_id,
    title: taskForm.title.trim(),
    description: taskForm.description,
    points: Number(taskForm.points) || 0,
    task_type: taskForm.task_type,
    requires_photo: taskForm.requires_photo,
    active: taskForm.active,
  }
  try {
    if (editingTask.value) {
      await api.updateTask(editingTask.value.id, base)
    } else {
      const payload: TaskPayload = { ...base, child_id: taskForm.child_id }
      await api.createTask(payload)
    }
    message.success('任务已保存')
    taskOpen.value = false
    await load()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '保存失败')
  }
}

// ---------------------------------------------------------------------------
// Rewards
// ---------------------------------------------------------------------------

const rewardOpen = ref(false)
const editingReward = ref<Reward | null>(null)
const rewardForm = reactive({
  title: '',
  emoji: '🎁',
  description: '',
  value: 50,
  unit: 'points' as RewardUnit,
  multiplier: 1,
  stock: -1,
  is_long_term: false,
  active: true,
})

const rewardCostPreview = computed(() =>
  Math.max(0, Math.ceil((Number(rewardForm.value) || 0) * (Number(rewardForm.multiplier) || 0))),
)

function openNewReward() {
  editingReward.value = null
  Object.assign(rewardForm, {
    title: '',
    emoji: '🎁',
    description: '',
    value: 50,
    unit: 'points',
    multiplier: 1,
    stock: -1,
    is_long_term: false,
    active: true,
  })
  rewardOpen.value = true
}

function openEditReward(reward: Reward) {
  editingReward.value = reward
  Object.assign(rewardForm, {
    title: reward.title,
    emoji: reward.emoji,
    description: reward.description,
    value: reward.value,
    unit: reward.unit,
    multiplier: reward.multiplier,
    stock: reward.stock,
    is_long_term: reward.is_long_term,
    active: reward.active,
  })
  rewardOpen.value = true
}

async function saveReward() {
  if (!rewardForm.title.trim()) {
    message.warning('奖励需要名字')
    return
  }
  if (Number(rewardForm.multiplier) <= 0) {
    message.warning('倍率需要大于 0')
    return
  }
  const payload: RewardPayload = {
    title: rewardForm.title.trim(),
    emoji: rewardForm.emoji,
    description: rewardForm.description,
    value: Number(rewardForm.value) || 0,
    unit: rewardForm.unit,
    multiplier: Number(rewardForm.multiplier) || 1,
    stock: Number(rewardForm.stock),
    is_long_term: rewardForm.is_long_term,
    active: rewardForm.active,
  }
  try {
    if (editingReward.value) {
      await api.updateReward(editingReward.value.id, payload)
    } else {
      await api.createReward(payload)
    }
    message.success('奖励已保存')
    rewardOpen.value = false
    await load()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '保存失败')
  }
}

function deactivateReward(reward: Reward) {
  dialog.warning({
    title: '下架这个奖励？',
    content: `「${reward.title}」会从孩子的心愿商店中移除。已经提交的兑换申请不受影响。`,
    positiveText: '下架',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await api.deactivateReward(reward.id)
        message.success('奖励已下架')
        await load()
      } catch (err) {
        message.error(err instanceof Error ? err.message : '下架失败')
      }
    },
  })
}

// ---------------------------------------------------------------------------
// Shared
// ---------------------------------------------------------------------------

async function backup() {
  try {
    const result = await api.backup()
    message.success(`已备份：${result.filename}`)
  } catch (err) {
    message.error(err instanceof Error ? err.message : '备份失败')
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [memberData, goalData, taskData, rewardData] = await Promise.all([
      api.members(),
      api.goals(undefined, true),
      api.tasks(undefined, true),
      api.rewards(undefined, true),
    ])
    members.value = memberData
    goals.value = goalData
    tasks.value = taskData
    rewards.value = rewardData
    if (
      !selectedChildId.value ||
      !children.value.some((child) => child.id === selectedChildId.value)
    ) {
      selectedChildId.value = children.value[0]?.id ?? null
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : '管理数据暂时打不开'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-if="loading" class="loading-state">
    <n-spin size="large" />
  </div>

  <main v-else class="parent-shell page-enter">
    <ParentNav />

    <header class="parent-title">
      <p class="eyebrow">FAMILY SETTINGS</p>
      <h1>管理中心</h1>
      <p>成员、目标、任务和奖励都可以在这里调整。</p>
    </header>

    <div v-if="error">
      <EmptyState emoji="🫙" title="管理数据暂时打不开" :text="error" />
    </div>

    <template v-else>
      <div class="manage-tabs">
        <button
          type="button"
          :class="{ active: activeTab === 'members' }"
          @click="activeTab = 'members'"
        >
          成员
        </button>
        <button
          type="button"
          :class="{ active: activeTab === 'goals' }"
          @click="activeTab = 'goals'"
        >
          目标
        </button>
        <button
          type="button"
          :class="{ active: activeTab === 'tasks' }"
          @click="activeTab = 'tasks'"
        >
          任务
        </button>
        <button
          type="button"
          :class="{ active: activeTab === 'rewards' }"
          @click="activeTab = 'rewards'"
        >
          奖励
        </button>
      </div>

      <section v-if="activeTab === 'members'" class="panel">
        <div class="manage-toolbar">
          <div class="panel-head" style="margin: 0">
            <div>
              <h2>家庭成员</h2>
              <p class="hint">每位成员都有自己的 PIN</p>
            </div>
          </div>
          <n-button type="primary" @click="openNewMember">添加成员</n-button>
        </div>
        <div class="manage-list">
          <div v-for="member in members" :key="member.id" class="manage-row">
            <div class="row-main">
              <strong>{{ member.avatar }} {{ member.name }}</strong>
              <span>
                {{ member.role === 'parent' ? '家长' : '孩子' }}
                · {{ member.is_active ? '启用' : '停用' }}
                <template v-if="member.role === 'child'">
                  · {{ member.approval_required ? '提交需审核' : '自动通过' }}
                </template>
              </span>
            </div>
            <div class="row-actions">
              <n-button size="small" tertiary @click="openEditMember(member)">
                编辑
              </n-button>
            </div>
          </div>
        </div>
      </section>

      <section v-if="activeTab === 'goals'" class="panel">
        <div class="manage-toolbar">
          <div class="panel-head" style="margin: 0">
            <div>
              <h2>目标</h2>
              <p class="hint">目标进度来自关联任务获得的积分</p>
            </div>
          </div>
          <div style="display: flex; gap: 8px; flex-wrap: wrap">
            <select v-model="selectedChildId" class="native-input" style="width: auto">
              <option :value="null">全部孩子</option>
              <option v-for="child in children" :key="child.id" :value="child.id">
                {{ child.avatar }} {{ child.name }}
              </option>
            </select>
            <n-button type="primary" @click="openNewGoal">添加目标</n-button>
          </div>
        </div>
        <div v-if="filteredGoals.length === 0" class="manage-list">
          <EmptyState emoji="🎯" title="还没有目标" text="先定一个孩子想靠近的小目标。" />
        </div>
        <div v-else class="manage-list">
          <div v-for="goal in filteredGoals" :key="goal.id" class="manage-row">
            <div class="row-main">
              <strong>{{ goal.emoji }} {{ goal.title }}</strong>
              <span>
                {{ goal.earned_points }} / {{ goal.target_points }} 积分 ·
                {{ goal.task_count }} 个任务 · {{ goal.progress_percent }}%
              </span>
            </div>
            <div class="row-actions">
              <n-button size="small" tertiary @click="openEditGoal(goal)">编辑</n-button>
              <n-button size="small" tertiary @click="deleteGoal(goal)">删除</n-button>
            </div>
          </div>
        </div>
      </section>

      <section v-if="activeTab === 'tasks'" class="panel">
        <div class="manage-toolbar">
          <div class="panel-head" style="margin: 0">
            <div>
              <h2>任务</h2>
              <p class="hint">每日、每周和一次性任务</p>
            </div>
          </div>
          <div style="display: flex; gap: 8px; flex-wrap: wrap">
            <select v-model="selectedChildId" class="native-input" style="width: auto">
              <option :value="null">全部孩子</option>
              <option v-for="child in children" :key="child.id" :value="child.id">
                {{ child.avatar }} {{ child.name }}
              </option>
            </select>
            <n-button type="primary" @click="openNewTask">添加任务</n-button>
          </div>
        </div>
        <div v-if="filteredTasks.length === 0" class="manage-list">
          <EmptyState emoji="📋" title="还没有任务" text="给孩子安排一件今天就能做的小事。" />
        </div>
        <div v-else class="manage-list">
          <div v-for="task in filteredTasks" :key="task.id" class="manage-row">
            <div class="row-main">
              <strong>{{ task.title }}</strong>
              <span>
                +{{ task.points }} 积分 · {{ taskTypeLabel(task.task_type) }}
                · {{ task.active ? '启用' : '停用' }}
                <template v-if="task.goal_title"> · {{ task.goal_title }}</template>
                <template v-if="task.requires_photo"> · 需照片</template>
              </span>
            </div>
            <div class="row-actions">
              <n-button size="small" tertiary @click="openEditTask(task)">编辑</n-button>
            </div>
          </div>
        </div>
      </section>

      <section v-if="activeTab === 'rewards'" class="panel">
        <div class="manage-toolbar">
          <div class="panel-head" style="margin: 0">
            <div>
              <h2>奖励与心愿</h2>
              <p class="hint">倍率越高，同样价值需要更多积分</p>
            </div>
          </div>
          <div style="display: flex; gap: 8px; flex-wrap: wrap">
            <n-button tertiary @click="backup">立即备份</n-button>
            <n-button type="primary" @click="openNewReward">添加奖励</n-button>
          </div>
        </div>
        <div v-if="rewards.length === 0" class="manage-list">
          <EmptyState emoji="🎁" title="还没有奖励" text="上架一个值得期待的奖励。" />
        </div>
        <div v-else class="manage-list">
          <div v-for="reward in rewards" :key="reward.id" class="manage-row">
            <div class="row-main">
              <strong>{{ reward.emoji }} {{ reward.title }}</strong>
              <span>
                {{ reward.value }} {{ reward.unit }} × {{ reward.multiplier }}
                = {{ reward.cost_points }} 积分 ·
                {{ reward.stock === -1 ? '不限量' : `库存 ${reward.stock}` }}
                · {{ reward.is_long_term ? '长期心愿' : '普通奖励' }}
                · {{ reward.active ? '上架中' : '已下架' }}
              </span>
            </div>
            <div class="row-actions">
              <n-button size="small" tertiary @click="openEditReward(reward)">
                编辑
              </n-button>
              <n-button
                v-if="reward.active"
                size="small"
                tertiary
                @click="deactivateReward(reward)"
              >
                下架
              </n-button>
            </div>
          </div>
        </div>
      </section>
    </template>

    <n-modal
      v-model:show="memberOpen"
      preset="card"
      :title="editingMember ? '编辑成员' : '添加成员'"
      :style="{ width: 'min(520px, 92vw)' }"
    >
      <div class="modal-form">
        <div class="field">
          <label>名字</label>
          <n-input v-model:value="memberForm.name" maxlength="50" />
        </div>
        <div class="field-row">
          <div class="field">
            <label>头像</label>
            <select v-model="memberForm.avatar" class="native-input">
              <option v-for="emoji in emojiChoices" :key="emoji" :value="emoji">
                {{ emoji }}
              </option>
            </select>
          </div>
          <div class="field">
            <label>角色</label>
            <select
              v-model="memberForm.role"
              class="native-input"
              :disabled="Boolean(editingMember)"
            >
              <option v-for="option in roleOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </div>
        </div>
        <div class="field">
          <label>{{ editingMember ? '新 PIN（留空不修改）' : 'PIN（4 位数字）' }}</label>
          <n-input
            v-model:value="memberForm.pin"
            type="password"
            maxlength="4"
            placeholder="4 位数字"
          />
        </div>
        <div v-if="memberForm.role === 'child'" class="check-row">
          <div>
            <strong>提交任务需要家长审核</strong>
            <span>关闭后孩子提交立即通过</span>
          </div>
          <n-switch v-model:value="memberForm.approval_required" />
        </div>
        <div v-if="editingMember" class="check-row">
          <div>
            <strong>启用账号</strong>
            <span>停用后该成员不能登录</span>
          </div>
          <n-switch v-model:value="memberForm.is_active" />
        </div>
      </div>
      <template #footer>
        <div class="modal-footer">
          <n-button @click="memberOpen = false">取消</n-button>
          <n-button type="primary" @click="saveMember">保存</n-button>
        </div>
      </template>
    </n-modal>

    <n-modal
      v-model:show="goalOpen"
      preset="card"
      :title="editingGoal ? '编辑目标' : '添加目标'"
      :style="{ width: 'min(560px, 92vw)' }"
    >
      <div class="modal-form">
        <div class="field">
          <label>孩子</label>
          <select v-model="goalForm.child_id" class="native-input">
            <option v-for="child in children" :key="child.id" :value="child.id">
              {{ child.avatar }} {{ child.name }}
            </option>
          </select>
        </div>
        <div class="field-row">
          <div class="field">
            <label>目标名字</label>
            <n-input v-model:value="goalForm.title" maxlength="100" />
          </div>
          <div class="field">
            <label>图标</label>
            <select v-model="goalForm.emoji" class="native-input">
              <option v-for="emoji in emojiChoices" :key="emoji" :value="emoji">
                {{ emoji }}
              </option>
            </select>
          </div>
        </div>
        <div class="field">
          <label>说明</label>
          <n-input
            v-model:value="goalForm.description"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 3 }"
          />
        </div>
        <div class="field-row three">
          <div class="field">
            <label>目标积分</label>
            <input v-model.number="goalForm.target_points" type="number" min="0" class="native-input" />
          </div>
          <div class="field">
            <label>开始日期</label>
            <input v-model="goalForm.start_date" type="date" class="native-input" />
          </div>
          <div class="field">
            <label>结束日期</label>
            <input v-model="goalForm.end_date" type="date" class="native-input" />
          </div>
        </div>
        <div v-if="editingGoal" class="field">
          <label>状态</label>
          <select v-model="goalForm.status" class="native-input">
            <option v-for="option in statusOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </div>
      </div>
      <template #footer>
        <div class="modal-footer">
          <n-button @click="goalOpen = false">取消</n-button>
          <n-button type="primary" @click="saveGoal">保存</n-button>
        </div>
      </template>
    </n-modal>

    <n-modal
      v-model:show="taskOpen"
      preset="card"
      :title="editingTask ? '编辑任务' : '添加任务'"
      :style="{ width: 'min(560px, 92vw)' }"
    >
      <div class="modal-form">
        <div class="field">
          <label>孩子</label>
          <select v-model="taskForm.child_id" class="native-input" :disabled="Boolean(editingTask)">
            <option v-for="child in children" :key="child.id" :value="child.id">
              {{ child.avatar }} {{ child.name }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>关联目标（可选）</label>
          <select v-model="taskForm.goal_id" class="native-input">
            <option :value="null">不关联目标</option>
            <option v-for="goal in taskGoalOptions" :key="goal.value" :value="goal.value">
              {{ goal.label }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>任务名字</label>
          <n-input v-model:value="taskForm.title" maxlength="100" />
        </div>
        <div class="field">
          <label>说明</label>
          <n-input
            v-model:value="taskForm.description"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 3 }"
          />
        </div>
        <div class="field-row three">
          <div class="field">
            <label>积分</label>
            <input v-model.number="taskForm.points" type="number" min="0" max="10000" class="native-input" />
          </div>
          <div class="field">
            <label>周期</label>
            <select v-model="taskForm.task_type" class="native-input">
              <option v-for="option in taskTypeOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </div>
          <div class="field">
            <label>状态</label>
            <select v-model="taskForm.active" class="native-input">
              <option :value="true">启用</option>
              <option :value="false">停用</option>
            </select>
          </div>
        </div>
        <div class="check-row">
          <div>
            <strong>需要照片凭证</strong>
            <span>孩子提交时必须上传一张照片</span>
          </div>
          <n-switch v-model:value="taskForm.requires_photo" />
        </div>
      </div>
      <template #footer>
        <div class="modal-footer">
          <n-button @click="taskOpen = false">取消</n-button>
          <n-button type="primary" @click="saveTask">保存</n-button>
        </div>
      </template>
    </n-modal>

    <n-modal
      v-model:show="rewardOpen"
      preset="card"
      :title="editingReward ? '编辑奖励' : '添加奖励'"
      :style="{ width: 'min(560px, 92vw)' }"
    >
      <div class="modal-form">
        <div class="field-row">
          <div class="field">
            <label>奖励名字</label>
            <n-input v-model:value="rewardForm.title" maxlength="100" />
          </div>
          <div class="field">
            <label>图标</label>
            <select v-model="rewardForm.emoji" class="native-input">
              <option v-for="emoji in emojiChoices" :key="emoji" :value="emoji">
                {{ emoji }}
              </option>
            </select>
          </div>
        </div>
        <div class="field">
          <label>说明</label>
          <n-input
            v-model:value="rewardForm.description"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 3 }"
          />
        </div>
        <div class="field-row three">
          <div class="field">
            <label>标价</label>
            <input v-model.number="rewardForm.value" type="number" min="0" class="native-input" />
          </div>
          <div class="field">
            <label>单位</label>
            <select v-model="rewardForm.unit" class="native-input">
              <option v-for="option in unitOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </div>
          <div class="field">
            <label>倍率</label>
            <input
              v-model.number="rewardForm.multiplier"
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
            <input v-model.number="rewardForm.stock" type="number" min="-1" class="native-input" />
          </div>
          <div class="field">
            <label>实际所需积分</label>
            <input :value="rewardCostPreview" class="native-input" disabled />
          </div>
          <div class="field">
            <label>状态</label>
            <select v-model="rewardForm.active" class="native-input">
              <option :value="true">上架</option>
              <option :value="false">下架</option>
            </select>
          </div>
        </div>
        <div class="check-row">
          <div>
            <strong>长期心愿</strong>
            <span>支持进度、预计天数和锁定储蓄</span>
          </div>
          <n-switch v-model:value="rewardForm.is_long_term" />
        </div>
        <p class="muted" style="font-size: 12px">
          所需积分 = ceil(标价 × 倍率)。倍率 1.0 是基准，大于 1 更贵，小于 1 更便宜。
        </p>
      </div>
      <template #footer>
        <div class="modal-footer">
          <n-button @click="rewardOpen = false">取消</n-button>
          <n-button type="primary" @click="saveReward">保存</n-button>
        </div>
      </template>
    </n-modal>
  </main>
</template>
