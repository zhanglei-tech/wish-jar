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

export interface Goal {
  id: number
  child_id: number
  title: string
  emoji: string
  description: string
  target_points: number
  start_date: string | null
  end_date: string | null
  status: 'active' | 'completed' | 'archived'
  earned_points: number
  progress_percent: number
  task_count: number
}

export interface Task {
  id: number
  child_id: number
  goal_id: number | null
  goal_title: string | null
  title: string
  description: string
  points: number
  task_type: TaskType
  requires_photo: boolean
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
  streak_days: number
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
  active: boolean
  locked_points: number
  progress_percent: number
  remaining_points: number
  estimated_days: number | null
  locks: SavingsLock[]
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
  streak_days: number
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
  description: string
  target_points: number
  start_date: string | null
  end_date: string | null
  status?: 'active' | 'completed' | 'archived'
}

export interface TaskPayload {
  child_id: number
  goal_id: number | null
  title: string
  description: string
  points: number
  task_type: TaskType
  requires_photo: boolean
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
  active: boolean
}

export interface ReviewPayload {
  approve: boolean
  note: string
}

export interface BackupResult {
  filename: string
  created_at: string
}
