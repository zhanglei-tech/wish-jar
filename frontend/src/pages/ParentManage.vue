<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
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
import VersionLabel from '../components/VersionLabel.vue'
import type {
  Goal,
  GoalPayload,
  GoalStagePayload,
  LevelThreshold,
  MemberOut,
  MemberPayload,
  ProgressMode,
  Reward,
  RewardPayload,
  RewardUnit,
  Role,
  Task,
  TaskPayload,
  TaskType,
  WishMatch,
} from '../types'
import { emojiChoices, taskTypeLabel } from '../utils'

type Tab = 'members' | 'goals' | 'tasks' | 'rewards' | 'levels'
type StageDraft = GoalStagePayload & { badge_image_url?: string | null }

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
const levelThresholds = ref<LevelThreshold[]>([])
const levelsSaving = ref(false)

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
const goalIconUrl = ref<string | null>(null)
const goalBadgeUrl = ref<string | null>(null)
const goalForm = reactive({
  child_id: null as number | null,
  title: '',
  emoji: '🎯',
  description: '',
  progress_mode: 'points' as ProgressMode,
  target_value: 100,
  icon_image_path: null as string | null,
  badge_name: '',
  badge_emoji: '🏅',
  badge_image_path: null as string | null,
  start_date: '',
  end_date: '',
  status: 'active' as Goal['status'],
  stages: [] as StageDraft[],
})

const progressModeOptions: { label: string; value: ProgressMode }[] = [
  { label: '按积分', value: 'points' },
  { label: '按完成次数', value: 'task_count' },
]
const goalTargetLabel = computed(() =>
  goalForm.progress_mode === 'points' ? '目标积分' : '目标次数',
)

function addStage() {
  if (goalForm.stages.length >= 10) {
    message.warning('最多设置 10 个阶段')
    return
  }
  const previous = goalForm.stages[goalForm.stages.length - 1]
  const target = Number(goalForm.target_value) || 100
  const nextThreshold = previous
    ? Math.min(target - 1, Number(previous.threshold_value) + Math.max(1, Math.floor(target / 4)))
    : Math.max(1, Math.floor(target / 4))
  goalForm.stages.push({
    threshold_value: Math.max(1, nextThreshold),
    badge_name: '',
    badge_emoji: '🏅',
    badge_image_path: null,
    badge_image_url: null,
  })
}

function removeStage(index: number) {
  goalForm.stages.splice(index, 1)
}

async function pickGoalImage(kind: 'icon' | 'badge', event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0] ?? null
  if (!file) return
  if (file.size > 2 * 1024 * 1024) {
    message.warning('图片不能超过 2MB')
    input.value = ''
    return
  }
  try {
    const result = await api.uploadIcon(file)
    if (kind === 'icon') {
      goalForm.icon_image_path = result.path
      goalIconUrl.value = result.url
    } else {
      goalForm.badge_image_path = result.path
      goalBadgeUrl.value = result.url
    }
    message.success('图片已上传')
  } catch (err) {
    message.error(err instanceof Error ? err.message : '图片上传失败')
  } finally {
    input.value = ''
  }
}

async function pickStageImage(index: number, event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0] ?? null
  if (!file) return
  if (file.size > 2 * 1024 * 1024) {
    message.warning('图片不能超过 2MB')
    input.value = ''
    return
  }
  try {
    const result = await api.uploadIcon(file)
    const stage = goalForm.stages[index]
    if (stage) {
      stage.badge_image_path = result.path
      stage.badge_image_url = result.url
    }
    message.success('阶段徽章图片已上传')
  } catch (err) {
    message.error(err instanceof Error ? err.message : '图片上传失败')
  } finally {
    input.value = ''
  }
}

function openNewGoal() {
  const child = selectedChildId.value ?? children.value[0]?.id ?? null
  if (!child) {
    message.warning('先添加一个孩子账号')
    return
  }
  editingGoal.value = null
  goalIconUrl.value = null
  goalBadgeUrl.value = null
  Object.assign(goalForm, {
    child_id: child,
    title: '',
    emoji: '🎯',
    description: '',
    progress_mode: 'points',
    target_value: 100,
    icon_image_path: null,
    badge_name: '',
    badge_emoji: '🏅',
    badge_image_path: null,
    start_date: '',
    end_date: '',
    status: 'active',
    stages: [],
  })
  goalOpen.value = true
}

function openEditGoal(goal: Goal) {
  editingGoal.value = goal
  goalIconUrl.value = goal.icon_url
  goalBadgeUrl.value = goal.badge_image_url
  Object.assign(goalForm, {
    child_id: goal.child_id,
    title: goal.title,
    emoji: goal.emoji,
    description: goal.description,
    progress_mode: goal.progress_mode,
    target_value: goal.target_value || goal.target_points,
    icon_image_path: null,
    badge_name: goal.badge_name,
    badge_emoji: goal.badge_emoji || '🏅',
    badge_image_path: null,
    start_date: goal.start_date ?? '',
    end_date: goal.end_date ?? '',
    status: goal.status,
    stages: goal.stages.map((stage) => ({
      id: stage.id,
      threshold_value: stage.threshold_value,
      badge_name: stage.badge_name,
      badge_emoji: stage.badge_emoji,
      badge_image_path: stage.badge_image_path,
      badge_image_url: stage.badge_image_url,
    })),
  })
  goalOpen.value = true
}

async function saveGoal() {
  if (!goalForm.child_id || !goalForm.title.trim()) {
    message.warning('请选择孩子并填写目标名字')
    return
  }
  const target = Number(goalForm.target_value) || 0
  if (target <= 0) {
    message.warning(`${goalTargetLabel.value}需要大于 0`)
    return
  }
  const stages = goalForm.stages.map((stage) => ({
    ...(stage.id ? { id: stage.id } : {}),
    threshold_value: Number(stage.threshold_value) || 0,
    badge_name: stage.badge_name.trim(),
    badge_emoji: stage.badge_emoji,
    badge_image_path: stage.badge_image_path,
  }))
  let previous = 0
  for (const stage of stages) {
    if (stage.threshold_value <= previous) {
      message.warning('阶段门槛需要从小到大、严格递增')
      return
    }
    if (stage.threshold_value >= target) {
      message.warning('阶段门槛需要小于目标值')
      return
    }
    previous = stage.threshold_value
  }
  const base = {
    child_id: goalForm.child_id,
    title: goalForm.title.trim(),
    emoji: goalForm.emoji,
    description: goalForm.description,
    progress_mode: goalForm.progress_mode,
    target_value: target,
    badge_name: goalForm.badge_name.trim(),
    badge_emoji: goalForm.badge_emoji.trim(),
    start_date: goalForm.start_date || null,
    end_date: goalForm.end_date || null,
    stages,
  }
  try {
    if (editingGoal.value) {
      const update: Partial<GoalPayload> = {
        ...base,
        status: goalForm.status,
      }
      if (goalIconUrl.value !== editingGoal.value.icon_url) {
        update.icon_image_path = goalForm.icon_image_path
      }
      if (goalBadgeUrl.value !== editingGoal.value.badge_image_url) {
        update.badge_image_path = goalForm.badge_image_path
      }
      await api.updateGoal(editingGoal.value.id, update)
    } else {
      await api.createGoal({
        ...base,
        icon_image_path: goalForm.icon_image_path,
        badge_image_path: goalForm.badge_image_path,
      })
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
  reward_id: null as number | null,
  title: '',
  description: '',
  points: 20,
  task_type: 'daily' as TaskType,
  requires_photo: false,
  active: true,
  active_weekdays: [1, 2, 3, 4, 5, 6, 7] as number[],
  streak_threshold_days: 7,
  streak_bonus_percent: 25,
})

const weekdayOptions = [
  { value: 1, label: '一' },
  { value: 2, label: '二' },
  { value: 3, label: '三' },
  { value: 4, label: '四' },
  { value: 5, label: '五' },
  { value: 6, label: '六' },
  { value: 7, label: '日' },
]

const taskGoalOptions = computed(() =>
  goals.value
    .filter((goal) => goal.child_id === taskForm.child_id)
    .map((goal) => ({ label: `${goal.emoji} ${goal.title}`, value: goal.id })),
)
const taskRewardOptions = computed(() =>
  rewards.value
    .filter((reward) => reward.active)
    .map((reward) => ({ label: `${reward.emoji} ${reward.title}`, value: reward.id })),
)

function toggleWeekday(day: number) {
  const index = taskForm.active_weekdays.indexOf(day)
  if (index >= 0) {
    if (taskForm.active_weekdays.length === 1) {
      message.warning('至少保留一天')
      return
    }
    taskForm.active_weekdays.splice(index, 1)
  } else {
    taskForm.active_weekdays.push(day)
    taskForm.active_weekdays.sort((a, b) => a - b)
  }
}

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
    reward_id: null,
    title: '',
    description: '',
    points: 20,
    task_type: 'daily',
    requires_photo: false,
    active: true,
    active_weekdays: [1, 2, 3, 4, 5, 6, 7],
    streak_threshold_days: 7,
    streak_bonus_percent: 25,
  })
  taskOpen.value = true
}

function openEditTask(task: Task) {
  editingTask.value = task
  Object.assign(taskForm, {
    child_id: task.child_id,
    goal_id: task.goal_id,
    reward_id: task.reward_id,
    title: task.title,
    description: task.description,
    points: task.points,
    task_type: task.task_type,
    requires_photo: task.requires_photo,
    active: task.active,
    active_weekdays: [...task.active_weekdays],
    streak_threshold_days: task.streak_threshold_days,
    streak_bonus_percent: task.streak_bonus_percent,
  })
  taskOpen.value = true
}

async function saveTask() {
  if (!taskForm.child_id || !taskForm.title.trim()) {
    message.warning('请选择孩子并填写任务名字')
    return
  }
  if (taskForm.active_weekdays.length === 0) {
    message.warning('至少选择一个适用星期')
    return
  }
  const weekdays =
    taskForm.task_type === 'daily' ? [...taskForm.active_weekdays] : [1, 2, 3, 4, 5, 6, 7]
  const base = {
    goal_id: taskForm.goal_id,
    reward_id: taskForm.reward_id,
    title: taskForm.title.trim(),
    description: taskForm.description,
    points: Number(taskForm.points) || 0,
    task_type: taskForm.task_type,
    requires_photo: taskForm.requires_photo,
    active: taskForm.active,
    active_weekdays: weekdays,
    streak_threshold_days: Number(taskForm.streak_threshold_days) || 7,
    streak_bonus_percent: Number(taskForm.streak_bonus_percent) || 0,
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

function weekdayLabel(days: number[]) {
  if (days.length === 7) return '每天'
  return days.map((day) => `周${weekdayOptions.find((item) => item.value === day)?.label ?? day}`).join('、')
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
  auto_match_percent: 0,
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
    auto_match_percent: 0,
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
    auto_match_percent: reward.auto_match_percent,
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
    auto_match_percent: Number(rewardForm.auto_match_percent) || 0,
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
// Matching and levels
// ---------------------------------------------------------------------------

const matchOpen = ref(false)
const matchRewardId = ref<number | null>(null)
const matchDetail = ref<Reward | null>(null)
const matchList = ref<WishMatch[]>([])
const matchingSaving = ref(false)
const matchForm = reactive({
  child_id: null as number | null,
  amount: 50,
  note: '',
})

const matchReward = computed(
  () => rewards.value.find((reward) => reward.id === matchRewardId.value) ?? null,
)
const activeMatches = computed(() =>
  matchList.value.filter((match) => match.status === 'active'),
)

async function loadMatchDetail() {
  if (!matchRewardId.value || !matchForm.child_id) return
  const [detail, list] = await Promise.all([
    api.reward(matchRewardId.value, matchForm.child_id),
    api.matches({
      childId: matchForm.child_id,
      rewardId: matchRewardId.value,
    }),
  ])
  matchDetail.value = detail
  matchList.value = list
}

function openMatches(reward: Reward) {
  matchRewardId.value = reward.id
  matchDetail.value = reward
  matchList.value = reward.matches
  matchForm.child_id = selectedChildId.value ?? children.value[0]?.id ?? null
  matchForm.amount = Math.max(10, Math.ceil(reward.cost_points / 10))
  matchForm.note = ''
  matchOpen.value = true
  loadMatchDetail().catch((err) => {
    message.error(err instanceof Error ? err.message : '配捐信息加载失败')
  })
}

watch(
  () => matchForm.child_id,
  () => {
    if (matchOpen.value) {
      loadMatchDetail().catch(() => {
        // The modal keeps the last loaded numbers; the user can retry by switching child.
      })
    }
  },
)

async function addMatch() {
  const reward = matchReward.value
  if (!reward || !matchForm.child_id) {
    message.warning('请选择孩子')
    return
  }
  if (Number(matchForm.amount) <= 0) {
    message.warning('配捐积分需要大于 0')
    return
  }
  matchingSaving.value = true
  try {
    await api.createMatch({
      reward_id: reward.id,
      child_id: matchForm.child_id,
      amount: Number(matchForm.amount),
      note: matchForm.note,
    })
    message.success('配捐已加入心愿')
    matchForm.note = ''
    await loadMatchDetail()
    await load()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '配捐失败')
  } finally {
    matchingSaving.value = false
  }
}

function revokeWishMatch(match: WishMatch) {
  dialog.warning({
    title: '撤销这笔配捐？',
    content: `撤销后 ${match.amount} 积分配捐将不再计入心愿。`,
    positiveText: '撤销',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await api.revokeMatch(match.id)
        message.success('配捐已撤销')
        await loadMatchDetail()
        await load()
      } catch (err) {
        message.error(err instanceof Error ? err.message : '撤销失败')
      }
    },
  })
}

const levelBase = ref(100)
const levelStep = ref(100)
let levelPresetInitialized = false

const invalidLevels = computed(() => {
  const invalid = new Set<number>()
  const rows = levelThresholds.value
  if (!rows.length) return invalid
  if (rows[0].required_points <= 0) invalid.add(rows[0].level)
  for (let index = 1; index < rows.length; index += 1) {
    if (rows[index].required_points <= rows[index - 1].required_points) {
      invalid.add(rows[index].level)
    }
  }
  return invalid
})

function applyLevelSequence() {
  const base = Number(levelBase.value)
  const step = Number(levelStep.value)
  if (base <= 0 || step <= 0) {
    message.warning('起点和每级增加都需要大于 0')
    return
  }
  dialog.warning({
    title: '按等差覆盖等级门槛？',
    content: `Lv.2 从 ${base} 开始，每级增加 ${step}，会覆盖下面所有门槛。`,
    positiveText: '生成',
    negativeText: '取消',
    onPositiveClick: () => {
      levelThresholds.value = levelThresholds.value.map((item, index) => ({
        ...item,
        required_points: base + step * index,
      }))
    },
  })
}

async function saveLevels() {
  if (invalidLevels.value.size > 0) {
    message.warning('门槛需要从 Lv.2 起逐级严格递增，请检查标红的等级')
    return
  }
  if (levelThresholds.value.some((item) => item.required_points > 10_000_000)) {
    message.warning('单个等级门槛不能超过 10,000,000')
    return
  }
  levelsSaving.value = true
  try {
    const result = await api.updateLevels(
      levelThresholds.value.map((item) => ({
        level: item.level,
        required_points: Number(item.required_points) || 0,
      })),
    )
    levelThresholds.value = result.thresholds
    if (result.thresholds.length >= 2) {
      levelBase.value = result.thresholds[0].required_points
      levelStep.value = Math.max(
        1,
        result.thresholds[1].required_points - result.thresholds[0].required_points,
      )
    }
    message.success('等级门槛已保存')
    await load()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '保存失败')
  } finally {
    levelsSaving.value = false
  }
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
    const [memberData, goalData, taskData, rewardData, levelData] = await Promise.all([
      api.members(),
      api.goals(undefined, true),
      api.tasks(undefined, true),
      api.rewards(undefined, true),
      api.levels(),
    ])
    members.value = memberData
    goals.value = goalData
    tasks.value = taskData
    rewards.value = rewardData
    levelThresholds.value = levelData.thresholds
    if (!levelPresetInitialized && levelData.thresholds.length >= 2) {
      levelBase.value = levelData.thresholds[0].required_points
      levelStep.value = Math.max(
        1,
        levelData.thresholds[1].required_points - levelData.thresholds[0].required_points,
      )
      levelPresetInitialized = true
    }
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
        <button
          type="button"
          :class="{ active: activeTab === 'levels' }"
          @click="activeTab = 'levels'"
        >
          等级
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
              <strong>
                <img v-if="goal.icon_url" :src="goal.icon_url" class="wish-thumb" alt="" />
                {{ goal.emoji }} {{ goal.title }}
              </strong>
              <span>
                {{ goal.progress_value }} / {{ goal.target_value }}
                {{ goal.progress_mode === 'points' ? '积分' : '次' }} ·
                {{ goal.progress_percent }}% · {{ goal.task_count }} 个任务
                <template v-if="goal.stages.length">
                  · {{ goal.stages.length }} 个阶段
                </template>
                <template v-if="goal.badge_name"> · 成就「{{ goal.badge_name }}」</template>
                <template v-if="goal.status === 'completed'"> · 已完成</template>
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
                <template v-if="task.goal_title"> · 目标 {{ task.goal_title }}</template>
                <template v-if="task.reward_title"> · 专属 {{ task.reward_title }}</template>
                <template v-if="task.requires_photo"> · 需照片</template>
                <template v-if="task.task_type === 'daily'">
                  · {{ weekdayLabel(task.active_weekdays) }}
                  · 连续 {{ task.streak_threshold_days }} 天 +{{ task.streak_bonus_percent }}%
                  <template v-if="task.streak_days"> · 当前 {{ task.streak_days }} 天</template>
                </template>
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
                <template v-if="reward.is_long_term && reward.auto_match_percent">
                  · 自动配捐 {{ reward.auto_match_percent }}%
                </template>
                <template v-if="reward.linked_tasks.length">
                  · {{ reward.linked_tasks.length }} 个专属任务
                </template>
              </span>
            </div>
            <div class="row-actions">
              <n-button
                v-if="reward.is_long_term"
                size="small"
                tertiary
                @click="openMatches(reward)"
              >
                配捐
              </n-button>
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

      <section v-if="activeTab === 'levels'" class="panel">
        <div class="manage-toolbar">
          <div class="panel-head" style="margin: 0">
            <div>
              <h2>等级门槛</h2>
              <p class="hint">累计获得积分达到门槛时自动升级，并授予等级徽章</p>
            </div>
          </div>
          <n-button type="primary" :loading="levelsSaving" @click="saveLevels">
            保存门槛
          </n-button>
        </div>
        <div class="level-tools">
          <div class="level-tool">
            <label>Lv.2 起点</label>
            <input v-model.number="levelBase" type="number" min="1" class="native-input" />
          </div>
          <div class="level-tool">
            <label>每级增加</label>
            <input v-model.number="levelStep" type="number" min="1" class="native-input" />
          </div>
          <n-button secondary type="primary" @click="applyLevelSequence">
            按等差生成
          </n-button>
          <span class="level-tools-hint">先快速生成，再单独微调任意等级</span>
        </div>

        <div class="level-grid">
          <div class="level-item level-item-base">
            <span class="level-tag">Lv.1</span>
            <span class="level-base-value">0</span>
            <span class="level-unit">积分</span>
            <span class="level-delta">起点</span>
          </div>
          <label
            v-for="(item, index) in levelThresholds"
            :key="item.level"
            class="level-item"
            :class="{ invalid: invalidLevels.has(item.level) }"
          >
            <span class="level-tag">Lv.{{ item.level }}</span>
            <input
              v-model.number="item.required_points"
              type="number"
              min="1"
              inputmode="numeric"
              class="native-input level-input"
            />
            <span class="level-unit">积分</span>
            <span class="level-delta">
              {{
                index === 0
                  ? '起点'
                  : `+${item.required_points - levelThresholds[index - 1].required_points}`
              }}
            </span>
          </label>
        </div>
        <p v-if="invalidLevels.size > 0" class="level-error">
          标红的门槛没有严格大于上一级，保存前需要修正。
        </p>
        <p v-else class="muted" style="font-size: 12px; margin-top: 10px">
          Lv.1 从 0 开始；右侧是相对上一级的增量。调整后已获得的等级徽章不会收回。
        </p>
      </section>
    </template>

    <VersionLabel class="parent-version" />

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
              <option
                v-if="memberForm.avatar && !emojiChoices.includes(memberForm.avatar)"
                :value="memberForm.avatar"
              >
                {{ memberForm.avatar }}
              </option>
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
      :style="{ width: 'min(640px, 94vw)' }"
    >
      <div class="modal-form">
        <div class="field-row">
          <div class="field">
            <label>孩子</label>
            <select v-model="goalForm.child_id" class="native-input">
              <option v-for="child in children" :key="child.id" :value="child.id">
                {{ child.avatar }} {{ child.name }}
              </option>
            </select>
          </div>
          <div class="field">
            <label>进度方式</label>
            <select
              v-model="goalForm.progress_mode"
              class="native-input"
              :disabled="Boolean(editingGoal)"
            >
              <option
                v-for="option in progressModeOptions"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}
              </option>
            </select>
          </div>
        </div>
        <div class="field-row">
          <div class="field">
            <label>目标名字</label>
            <n-input v-model:value="goalForm.title" maxlength="100" />
          </div>
          <div class="field">
            <label>图标 emoji</label>
            <select v-model="goalForm.emoji" class="native-input">
              <option
                v-if="goalForm.emoji && !emojiChoices.includes(goalForm.emoji)"
                :value="goalForm.emoji"
              >
                {{ goalForm.emoji }}
              </option>
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
        <div class="field">
          <label>自定义图标（可选，≤2MB）</label>
          <div class="image-pick-row">
            <img v-if="goalIconUrl" :src="goalIconUrl" class="wish-thumb" alt="目标图标" />
            <label class="file-button">
              选择图片
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                @change="pickGoalImage('icon', $event)"
              />
            </label>
            <button
              v-if="goalIconUrl"
              type="button"
              class="link-button"
              @click="goalIconUrl = null; goalForm.icon_image_path = null"
            >
              移除
            </button>
          </div>
        </div>
        <div class="field-row three">
          <div class="field">
            <label>{{ goalTargetLabel }}</label>
            <input v-model.number="goalForm.target_value" type="number" min="1" class="native-input" />
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

        <div class="field">
          <label>完成成就徽章</label>
          <div class="field-row three">
            <div class="field">
              <label>名字</label>
              <n-input v-model:value="goalForm.badge_name" maxlength="100" placeholder="例如：阅读小达人" />
            </div>
            <div class="field">
              <label>emoji</label>
              <n-input v-model:value="goalForm.badge_emoji" maxlength="16" />
            </div>
            <div class="field">
              <label>图片（可选）</label>
              <div class="image-pick-row">
                <img v-if="goalBadgeUrl" :src="goalBadgeUrl" class="wish-thumb" alt="成就徽章" />
                <label class="file-button">
                  选择
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    @change="pickGoalImage('badge', $event)"
                  />
                </label>
                <button
                  v-if="goalBadgeUrl"
                  type="button"
                  class="link-button"
                  @click="goalBadgeUrl = null; goalForm.badge_image_path = null"
                >
                  移除
                </button>
              </div>
            </div>
          </div>
        </div>

        <div class="field">
          <div class="stage-head">
            <label>阶段目标（可选，最多 10 个）</label>
            <button type="button" class="link-button" @click="addStage">+ 添加阶段</button>
          </div>
          <p class="hint" style="margin: 0 0 8px">
            阶段门槛小于目标值，达成时自动授予阶段徽章。
          </p>
          <div v-if="goalForm.stages.length" class="stage-list">
            <div
              v-for="(stage, index) in goalForm.stages"
              :key="stage.id ?? `new-${index}`"
              class="stage-row"
            >
              <div class="stage-head">
                <strong>阶段 {{ index + 1 }}</strong>
                <button type="button" class="link-button" @click="removeStage(index)">移除</button>
              </div>
              <div class="field-row three">
                <div class="field">
                  <label>达到{{ goalForm.progress_mode === 'points' ? '积分' : '次数' }}</label>
                  <input
                    v-model.number="stage.threshold_value"
                    type="number"
                    min="1"
                    class="native-input"
                  />
                </div>
                <div class="field">
                  <label>徽章名字</label>
                  <n-input v-model:value="stage.badge_name" maxlength="100" />
                </div>
                <div class="field">
                  <label>emoji</label>
                  <n-input v-model:value="stage.badge_emoji" maxlength="16" />
                </div>
              </div>
              <div class="image-pick-row">
                <img
                  v-if="stage.badge_image_url"
                  :src="stage.badge_image_url"
                  class="wish-thumb"
                  alt="阶段徽章"
                />
                <label class="file-button">
                  {{ stage.badge_image_url ? '更换徽章图片' : '上传徽章图片（可选）' }}
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    @change="pickStageImage(index, $event)"
                  />
                </label>
                <button
                  v-if="stage.badge_image_url"
                  type="button"
                  class="link-button"
                  @click="stage.badge_image_url = null; stage.badge_image_path = null"
                >
                  移除
                </button>
              </div>
            </div>
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
        <div class="field-row">
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
        </div>
        <div class="field">
          <label>奖励专属任务（可选）</label>
          <select v-model="taskForm.reward_id" class="native-input">
            <option :value="null">不关联奖励</option>
            <option v-for="reward in taskRewardOptions" :key="reward.value" :value="reward.value">
              {{ reward.label }}
            </option>
          </select>
          <p class="hint" style="margin: 4px 0 0">
            关联后，这个任务获得的积分会在奖励详情里作为“专属任务进度”展示，不直接抵扣积分。
          </p>
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
        <div v-if="taskForm.task_type === 'daily'" class="field">
          <label>适用星期</label>
          <div class="weekday-row">
            <button
              v-for="day in weekdayOptions"
              :key="day.value"
              type="button"
              class="weekday-chip"
              :class="{ active: taskForm.active_weekdays.includes(day.value) }"
              @click="toggleWeekday(day.value)"
            >
              {{ day.label }}
            </button>
          </div>
          <p class="hint" style="margin: 6px 0 0">
            只在选中的星期出现；不选的日期不计入连续打卡，也不会中断连续。
          </p>
        </div>
        <div v-if="taskForm.task_type === 'daily'" class="field-row three">
          <div class="field">
            <label>连续天数门槛</label>
            <input
              v-model.number="taskForm.streak_threshold_days"
              type="number"
              min="1"
              max="30"
              class="native-input"
            />
          </div>
          <div class="field">
            <label>额外奖励 %</label>
            <input
              v-model.number="taskForm.streak_bonus_percent"
              type="number"
              min="0"
              max="100"
              class="native-input"
            />
          </div>
          <div class="field">
            <label>示例奖励</label>
            <input
              :value="Math.ceil((Number(taskForm.points) || 0) * (Number(taskForm.streak_bonus_percent) || 0) / 100)"
              class="native-input"
              disabled
            />
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
              <option
                v-if="rewardForm.emoji && !emojiChoices.includes(rewardForm.emoji)"
                :value="rewardForm.emoji"
              >
                {{ rewardForm.emoji }}
              </option>
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
            <span>支持进度、预计天数、锁定储蓄和家长配捐</span>
          </div>
          <n-switch v-model:value="rewardForm.is_long_term" />
        </div>
        <div v-if="rewardForm.is_long_term" class="field">
          <label>自动配捐比例（0–100%）</label>
          <input
            v-model.number="rewardForm.auto_match_percent"
            type="number"
            min="0"
            max="100"
            class="native-input"
          />
          <p class="hint" style="margin: 4px 0 0">
            兑换时按当前锁定积分的这个比例自动配捐，最多补足心愿所需积分；不会增加余额。
          </p>
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

    <n-modal
      v-model:show="matchOpen"
      preset="card"
      :title="matchReward ? `配捐：${matchReward.emoji} ${matchReward.title}` : '配捐'"
      :style="{ width: 'min(560px, 92vw)' }"
    >
      <div v-if="matchDetail || matchReward" class="modal-form">
        <div class="wish-meta">
          <span class="pill">
            所需 {{ (matchDetail ?? matchReward)?.cost_points }} 积分
          </span>
          <span class="pill teal">
            已锁定 {{ (matchDetail ?? matchReward)?.locked_points }}
          </span>
          <span class="pill amber">
            已配捐 {{ (matchDetail ?? matchReward)?.matched_points }}
          </span>
          <span class="pill">
            自动配捐 {{ (matchDetail ?? matchReward)?.auto_match_percent }}%
          </span>
        </div>
        <p class="hint">
          自动配捐会在孩子兑换时按锁定积分计算；手动配捐由家长现在加入，兑换时先于可用余额使用。
        </p>

        <div v-if="activeMatches.length" class="stage-list">
          <div
            v-for="match in activeMatches"
            :key="match.id"
            class="stage-row"
          >
            <div class="row-main">
              <strong>
                {{ match.source === 'manual' ? '👨‍👩‍👧 家长配捐' : '✨ 自动配捐' }}
                · {{ match.amount }} 积分
              </strong>
              <span>
                {{ match.child_name }} · {{ match.parent_name || '系统' }}
                <template v-if="match.note"> · {{ match.note }}</template>
              </span>
            </div>
            <div class="row-actions">
              <n-button
                v-if="match.source === 'manual'"
                size="small"
                tertiary
                @click="revokeWishMatch(match)"
              >
                撤销
              </n-button>
              <span v-else class="pill amber">兑换时自动计算</span>
            </div>
          </div>
        </div>
        <p v-else class="muted" style="font-size: 13px">还没有生效中的配捐。</p>

        <div class="field-row three">
          <div class="field">
            <label>孩子</label>
            <select v-model="matchForm.child_id" class="native-input">
              <option v-for="child in children" :key="child.id" :value="child.id">
                {{ child.avatar }} {{ child.name }}
              </option>
            </select>
          </div>
          <div class="field">
            <label>配捐积分</label>
            <input v-model.number="matchForm.amount" type="number" min="1" class="native-input" />
          </div>
          <div class="field">
            <label>备注（可选）</label>
            <n-input v-model:value="matchForm.note" maxlength="100" />
          </div>
        </div>
        <n-button type="primary" :loading="matchingSaving" @click="addMatch">
          加入手动配捐
        </n-button>
      </div>
      <template #footer>
        <div class="modal-footer">
          <n-button @click="matchOpen = false">关闭</n-button>
        </div>
      </template>
    </n-modal>
  </main>
</template>
