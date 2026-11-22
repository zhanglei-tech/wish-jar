export type Role = 'parent' | 'child'
export type TaskType = 'daily' | 'weekly' | 'once'
export type TaskStatus = 'todo' | 'pending' | 'done' | 'rejected'
export type RewardUnit = 'points' | 'yuan' | 'minutes' | 'times'

export interface SetupStatus {
  needs_setup: boolean
  family_name: string | null
}

export interface MemberPublic {
  id: number
  name: string
  avatar: string
  role: Role
}

export interface MemberOut extends MemberPublic {
  approval_required: boolean
  is_active: boolean
}

export interface AuthMe {
  member: MemberOut
  family_name: string
}

export type ProgressMode = 'points' | 'task_count'
export type WishStatus = 'pending' | 'listed' | 'rejected'
export type StatsPeriod = 'week' | 'month' | 'quarter' | 'year'

export interface GoalStage {
  id: number
  threshold_value: number
  badge_name: string
  badge_emoji: string
  badge_image_path: string | null
  badge_image_url: string | null
  sort_order: number
  achieved: boolean
  badge_awarded: boolean
}

export interface GoalStagePayload {
  id?: number
  threshold_value: number
  badge_name: string
  badge_emoji: string
  badge_image_path: string | null
}

export interface Goal {
  id: number
  child_id: number
  title: string
  emoji: string
  icon_url: string | null
  description: string
  progress_mode: ProgressMode
  target_points: number
  target_value: number
  badge_name: string
  badge_emoji: string
  badge_image_url: string | null
  start_date: string | null
  end_date: string | null
  status: 'active' | 'completed' | 'archived'
  completed_at: string | null
  earned_points: number
  progress_value: number
  progress_percent: number
  task_count: number
  next_stage: GoalStage | null
  stages: GoalStage[]
}

export interface Badge {
  id: number
  kind: 'level' | 'achievement'
  level: number | null
  goal_id: number | null
  goal_stage_id: number | null
  goal_title: string | null
  name: string
  emoji: string
  image_url: string | null
  awarded_at: string
}

export interface Task {
  id: number
  child_id: number
  goal_id: number | null
  goal_title: string | null
  reward_id: number | null
  reward_title: string | null
  title: string
  description: string
  points: number
  task_type: TaskType
  requires_photo: boolean
  active_weekdays: number[]
  streak_threshold_days: number
  streak_bonus_percent: number
  streak_days: number
  bonus_active: boolean
  active: boolean
}

export interface TodayTask extends Task {
  child_name: string
  status: TaskStatus
  submission_id: number | null
}

export interface Submission {
  id: number
  task_id: number
  task_title: string
  child_id: number
  child_name: string
  submitted_by_id: number
  submitted_by_name: string
  status: 'pending' | 'approved' | 'rejected'
  note: string
  photo_url: string | null
  period_key: string
  submitted_at: string
  reviewed_by_id: number | null
  reviewed_at: string | null
  review_note: string
  points_awarded: number
  bonus_points: number
  bonus_percent: number
}

export interface Transaction {
  id: number
  delta: number
  kind: string
  ref_type: string | null
  ref_id: number | null
  note: string
  created_at: string
}

export interface PointSummary {
  child_id: number
  balance: number
  available: number
  locked: number
  lifetime_earned: number
  level: number
  level_progress: number
  next_level_points: number
  streak_days: number
  badges: Badge[]
  transactions: Transaction[]
}

export interface SavingsLock {
  id: number
  reward_id: number
  reward_title: string
  child_name: string
  amount: number
  status: 'active' | 'released' | 'redeemed'
  note: string
  created_at: string
  released_at: string | null
}

export interface WishMatch {
  id: number
  reward_id: number
  reward_title: string
  child_id: number
  child_name: string
  parent_name: string
  amount: number
  used_amount: number
  source: 'manual' | 'auto'
  status: 'active' | 'used' | 'voided' | 'revoked'
  note: string
  ratio_snapshot: number | null
  redemption_id: number | null
  created_at: string
  voided_at: string | null
}

export interface Reward {
  id: number
  title: string
  emoji: string
  description: string
  value: number
  unit: RewardUnit
  multiplier: number
  cost_points: number
  stock: number
  is_long_term: boolean
  auto_match_percent: number
  active: boolean
  locked_points: number
  manual_matched_points: number
  auto_match_points: number
  matched_points: number
  saved_points: number
  progress_percent: number
  remaining_points: number
  estimated_days: number | null
  locks: SavingsLock[]
  matches: WishMatch[]
  linked_tasks: Task[]
  reward_task_points: number
  reward_task_count: number
}

export interface Wish {
  id: number
  child_id: number
  child_name: string
  title: string
  emoji: string
  image_url: string | null
  reason: string
  expected_points: number
  status: WishStatus
  reward_id: number | null
  reward_title: string | null
  reject_reason: string
  created_at: string
  reviewed_at: string | null
}

export interface StatsBucket {
  label: string
  task_points: number
  bonus_points: number
  redeemed_points: number
  adjusted_points: number
  net_points: number
}

export interface Stats {
  child_id: number
  child_name: string
  period: StatsPeriod
  label: string
  start_date: string
  end_date: string
  task_points: number
  bonus_points: number
  redeemed_points: number
  adjusted_points: number
  net_points: number
  task_completion: {
    approved: number
    expected: number
    percent: number
  }
  redemption_count: number
  redemption_points: number
  redemption_statuses: Record<string, number>
  buckets: StatsBucket[]
  has_data: boolean
}

export interface LevelThreshold {
  level: number
  required_points: number
}

export interface Redemption {
  id: number
  reward_id: number
  reward_title: string
  reward_emoji: string
  child_id: number
  child_name: string
  cost_points: number
  multiplier_snapshot: number
  status: 'pending' | 'approved' | 'rejected' | 'fulfilled'
  requested_at: string
  reviewed_at: string | null
  review_note: string
  fulfilled_at: string | null
}

export interface ChildHome {
  member: MemberOut
  family_name: string
  balance: number
  available: number
  locked: number
  lifetime_earned: number
  level: number
  level_progress: number
  next_level_points: number
  streak_days: number
  badges: Badge[]
  today_tasks: TodayTask[]
  goals: Goal[]
  long_term_rewards: Reward[]
  recent_transactions: Transaction[]
  recent_redemptions: Redemption[]
}

export interface ChildSummary {
  member: MemberOut
  balance: number
  available: number
  locked: number
  week_earned: number
  level: number
}

export interface ParentDashboard {
  family_name: string
  children: ChildSummary[]
  pending_submissions: Submission[]
  pending_redemptions: Redemption[]
  unfulfilled_redemptions: Redemption[]
  pending_wish_count: number
  active_locks: SavingsLock[]
  today_tasks: TodayTask[]
}

export interface SetupPayload {
  family_name: string
  parent: {
    name: string
    avatar: string
    pin: string
  }
  child?: {
    name: string
    avatar: string
    pin: string
    approval_required: boolean
  }
  create_samples: boolean
}

export interface MemberPayload {
  name: string
  avatar: string
  role: Role
  pin?: string
  approval_required: boolean
  is_active?: boolean
}

export interface GoalPayload {
  child_id: number
  title: string
  emoji: string
  icon_image_path?: string | null
  description: string
  target_value?: number
  target_points?: number
  progress_mode?: ProgressMode
  badge_name?: string
  badge_emoji?: string
  badge_image_path?: string | null
  start_date: string | null
  end_date: string | null
  status?: 'active' | 'completed' | 'archived'
  stages?: GoalStagePayload[]
}

export interface TaskPayload {
  child_id: number
  goal_id: number | null
  reward_id: number | null
  title: string
  description: string
  points: number
  task_type: TaskType
  requires_photo: boolean
  active_weekdays: number[]
  streak_threshold_days: number
  streak_bonus_percent: number
  active: boolean
}

export interface RewardPayload {
  title: string
  emoji: string
  description: string
  value: number
  unit: RewardUnit
  multiplier: number
  stock: number
  is_long_term: boolean
  auto_match_percent: number
  active: boolean
}

export interface WishPayload {
  title: string
  emoji: string
  reason: string
  expected_points: number
  image?: File | null
}

export interface WishListPayload {
  title?: string
  emoji?: string
  description?: string
  value: number
  unit: RewardUnit
  multiplier: number
  stock: number
  is_long_term: boolean
  auto_match_percent: number
}

export interface MatchPayload {
  reward_id: number
  child_id: number
  amount: number
  note?: string
}

export interface ReviewPayload {
  approve: boolean
  note: string
}

export interface BackupResult {
  filename: string
  created_at: string
}
