import type {
  AuthMe,
  BackupResult,
  ChildHome,
  Goal,
  GoalPayload,
  MemberOut,
  MemberPayload,
  MemberPublic,
  ParentDashboard,
  PointSummary,
  Redemption,
  ReviewPayload,
  Reward,
  RewardPayload,
  SavingsLock,
  SetupPayload,
  SetupStatus,
  Submission,
  Task,
  TaskPayload,
  Transaction,
} from './types'

const API_BASE = '/api'

export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

interface RequestOptions {
  method?: string
  json?: unknown
  body?: BodyInit
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {}
  let body = options.body
  if (options.json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.json)
  }
  const response = await fetch(`${API_BASE}${path}`, {
    method: options.method ?? 'GET',
    headers,
    body,
    credentials: 'include',
  })
  if (!response.ok) {
    let detail = '请求失败，请稍后再试'
    try {
      const data = (await response.json()) as { detail?: unknown }
      if (typeof data.detail === 'string') detail = data.detail
      else if (Array.isArray(data.detail) && data.detail.length > 0) {
        detail = '提交的信息不完整，请检查后再试'
      }
    } catch {
      // Keep the friendly fallback.
    }
    if (response.status === 401 && path !== '/auth/login') {
      window.dispatchEvent(new Event('wishjar:unauthorized'))
    }
    throw new ApiError(response.status, detail)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

function query(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      search.set(key, String(value))
    }
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

export const api = {
  setupStatus: () => request<SetupStatus>('/setup/status'),
  setup: (payload: SetupPayload) =>
    request<AuthMe>('/setup', { method: 'POST', json: payload }),

  authMembers: () => request<MemberPublic[]>('/auth/members'),
  login: (memberId: number, pin: string) =>
    request<AuthMe>('/auth/login', {
      method: 'POST',
      json: { member_id: memberId, pin },
    }),
  logout: () => request<{ message: string }>('/auth/logout', { method: 'POST' }),
  me: () => request<AuthMe>('/auth/me'),

  members: () => request<MemberOut[]>('/members'),
  createMember: (payload: MemberPayload) =>
    request<MemberOut>('/members', { method: 'POST', json: payload }),
  updateMember: (id: number, payload: Partial<MemberPayload>) =>
    request<MemberOut>(`/members/${id}`, { method: 'PATCH', json: payload }),

  goals: (childId?: number, includeArchived = false) =>
    request<Goal[]>(
      `/goals${query({ child_id: childId, include_archived: includeArchived })}`,
    ),
  createGoal: (payload: GoalPayload) =>
    request<Goal>('/goals', { method: 'POST', json: payload }),
  updateGoal: (id: number, payload: Partial<GoalPayload>) =>
    request<Goal>(`/goals/${id}`, { method: 'PATCH', json: payload }),
  deleteGoal: (id: number) =>
    request<{ message: string }>(`/goals/${id}`, { method: 'DELETE' }),

  tasks: (childId?: number, includeInactive = false) =>
    request<Task[]>(
      `/tasks${query({ child_id: childId, include_inactive: includeInactive })}`,
    ),
  createTask: (payload: TaskPayload) =>
    request<Task>('/tasks', { method: 'POST', json: payload }),
  updateTask: (id: number, payload: Partial<TaskPayload>) =>
    request<Task>(`/tasks/${id}`, { method: 'PATCH', json: payload }),

  submitTask: (taskId: number, note: string, photo?: File | null) => {
    const form = new FormData()
    form.set('task_id', String(taskId))
    form.set('note', note)
    if (photo) form.set('photo', photo)
    return request<Submission>('/submissions', { method: 'POST', body: form })
  },
  submissions: (params: {
    childId?: number
    status?: string
    limit?: number
  } = {}) =>
    request<Submission[]>(
      `/submissions${query({
        child_id: params.childId,
        status: params.status,
        limit: params.limit,
      })}`,
    ),
  pendingSubmissions: () => request<Submission[]>('/submissions/pending'),
  reviewSubmission: (id: number, payload: ReviewPayload) =>
    request<Submission>(`/submissions/${id}/review`, {
      method: 'POST',
      json: payload,
    }),

  points: (childId?: number, limit = 50) =>
    request<PointSummary>(`/points${query({ child_id: childId, limit })}`),
  adjustPoints: (childId: number, delta: number, note: string) =>
    request<Transaction>('/points/adjust', {
      method: 'POST',
      json: { child_id: childId, delta, note },
    }),

  rewards: (childId?: number, includeInactive = false) =>
    request<Reward[]>(
      `/rewards${query({ child_id: childId, include_inactive: includeInactive })}`,
    ),
  reward: (id: number, childId?: number) =>
    request<Reward>(`/rewards/${id}${query({ child_id: childId })}`),
  createReward: (payload: RewardPayload) =>
    request<Reward>('/rewards', { method: 'POST', json: payload }),
  updateReward: (id: number, payload: Partial<RewardPayload>) =>
    request<Reward>(`/rewards/${id}`, { method: 'PATCH', json: payload }),
  deactivateReward: (id: number) =>
    request<{ message: string }>(`/rewards/${id}`, { method: 'DELETE' }),

  redemptions: (params: {
    childId?: number
    status?: string
    limit?: number
  } = {}) =>
    request<Redemption[]>(
      `/redemptions${query({
        child_id: params.childId,
        status: params.status,
        limit: params.limit,
      })}`,
    ),
  requestRedemption: (rewardId: number) =>
    request<Redemption>('/redemptions', {
      method: 'POST',
      json: { reward_id: rewardId },
    }),
  reviewRedemption: (id: number, payload: ReviewPayload) =>
    request<Redemption>(`/redemptions/${id}/review`, {
      method: 'POST',
      json: payload,
    }),
  fulfillRedemption: (id: number) =>
    request<Redemption>(`/redemptions/${id}/fulfill`, { method: 'POST' }),

  savings: (childId?: number, includeReleased = false) =>
    request<SavingsLock[]>(
      `/savings${query({
        child_id: childId,
        include_released: includeReleased,
      })}`,
    ),
  lockSavings: (rewardId: number, amount: number, note = '') =>
    request<SavingsLock>('/savings/lock', {
      method: 'POST',
      json: { reward_id: rewardId, amount, note },
    }),
  releaseSavings: (id: number) =>
    request<SavingsLock>(`/savings/${id}/release`, { method: 'POST' }),

  childHome: () => request<ChildHome>('/child/home'),
  parentDashboard: () => request<ParentDashboard>('/parent/dashboard'),
  backup: () => request<BackupResult>('/backup', { method: 'POST' }),
}
