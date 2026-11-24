import type { Redemption, RewardUnit, SavingsLock, Submission, TaskType } from './types'

export const emojiChoices = [
  '🦉',
  '🦊',
  '🐻',
  '🐼',
  '🐯',
  '🌱',
  '🌻',
  '🌈',
  '⭐',
  '🎯',
  '📚',
  '🎮',
  '💻',
  '💵',
  '🎬',
  '🍦',
  '🏕️',
  '🎨',
]

export function formatDate(value: string | null | undefined): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'long',
    day: 'numeric',
  }).format(date)
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export function todayLabel(): string {
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  }).format(new Date())
}

export function taskTypeLabel(type: TaskType): string {
  if (type === 'daily') return '每天'
  if (type === 'weekly') return '每周'
  return '一次'
}

export function unitLabel(unit: RewardUnit): string {
  if (unit === 'yuan') return '元'
  if (unit === 'minutes') return '分钟'
  if (unit === 'times') return '次'
  return '积分'
}

export function rewardValueLabel(value: number, unit: RewardUnit): string {
  if (unit === 'points') return `${value} 积分`
  return `${value} ${unitLabel(unit)}`
}

export function submissionStatusLabel(status: Submission['status']): string {
  if (status === 'pending') return '待审核'
  if (status === 'approved') return '已通过'
  return '已驳回'
}

export function redemptionStatusLabel(status: Redemption['status']): string {
  if (status === 'pending') return '待审核'
  if (status === 'approved') return '待兑现'
  if (status === 'fulfilled') return '已兑现'
  return '已驳回'
}

export function lockStatusLabel(status: SavingsLock['status']): string {
  if (status === 'active') return '锁定中'
  if (status === 'redeemed') return '已用于兑换'
  return '已释放'
}

export function greeting(): string {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了'
  if (hour < 11) return '早上好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
}

export function transactionKindLabel(kind: string): string {
  if (kind === 'parent_task') return '家长任务'
  if (kind === 'task') return '任务'
  if (kind === 'streak_bonus') return '连续奖励'
  if (kind === 'redeem') return '兑换'
  return '调整'
}

export function signedPoints(delta: number): string {
  return `${delta > 0 ? '+' : ''}${delta}`
}
