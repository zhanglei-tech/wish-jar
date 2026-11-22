from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Pin = Annotated[
    str, StringConstraints(min_length=4, max_length=4, pattern=r"^\d{4}$")
]
Role = Literal["parent", "child"]
TaskType = Literal["daily", "weekly", "once"]
TaskStatus = Literal["todo", "pending", "done", "rejected"]
RewardUnit = Literal["points", "yuan", "minutes", "times"]
GoalStatus = Literal["active", "completed", "archived"]


# ---------------------------------------------------------------------------
# Auth and setup
# ---------------------------------------------------------------------------


class SetupStatus(BaseModel):
    needs_setup: bool
    family_name: str | None = None


class ParentSetup(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    avatar: str = Field(default="🦉", max_length=16)
    pin: Pin


class ChildSetup(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    avatar: str = Field(default="🌱", max_length=16)
    pin: Pin
    approval_required: bool = True


class SetupRequest(BaseModel):
    family_name: str = Field(min_length=1, max_length=100)
    parent: ParentSetup
    child: ChildSetup | None = None
    create_samples: bool = False


class LoginRequest(BaseModel):
    member_id: int
    pin: Pin


class MemberPublic(BaseModel):
    id: int
    name: str
    avatar: str
    role: Role


class MemberOut(MemberPublic):
    approval_required: bool
    is_active: bool


class AuthMe(BaseModel):
    member: MemberOut
    family_name: str


class MemberCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    avatar: str = Field(default="🌱", max_length=16)
    role: Role
    pin: Pin
    approval_required: bool = True


class MemberUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    avatar: str | None = Field(default=None, max_length=16)
    approval_required: bool | None = None
    is_active: bool | None = None
    pin: Pin | None = None


# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------


class GoalCreate(BaseModel):
    child_id: int
    title: str = Field(min_length=1, max_length=100)
    emoji: str = Field(default="🎯", max_length=16)
    description: str = ""
    target_points: int = Field(default=0, ge=0, le=1_000_000)
    start_date: date | None = None
    end_date: date | None = None


class GoalUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    emoji: str | None = Field(default=None, max_length=16)
    description: str | None = None
    target_points: int | None = Field(default=None, ge=0, le=1_000_000)
    start_date: date | None = None
    end_date: date | None = None
    status: GoalStatus | None = None


class GoalOut(BaseModel):
    id: int
    child_id: int
    title: str
    emoji: str
    description: str
    target_points: int
    start_date: date | None
    end_date: date | None
    status: str
    earned_points: int
    progress_percent: int
    task_count: int


# ---------------------------------------------------------------------------
# Tasks and submissions
# ---------------------------------------------------------------------------


class TaskCreate(BaseModel):
    child_id: int
    goal_id: int | None = None
    title: str = Field(min_length=1, max_length=100)
    description: str = ""
    points: int = Field(default=0, ge=0, le=10000)
    task_type: TaskType = "daily"
    requires_photo: bool = False
    active: bool = True


class TaskUpdate(BaseModel):
    goal_id: int | None = None
    title: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    points: int | None = Field(default=None, ge=0, le=10000)
    task_type: TaskType | None = None
    requires_photo: bool | None = None
    active: bool | None = None


class TaskOut(BaseModel):
    id: int
    child_id: int
    goal_id: int | None
    goal_title: str | None
    title: str
    description: str
    points: int
    task_type: str
    requires_photo: bool
    active: bool


class TodayTaskOut(TaskOut):
    child_name: str
    status: TaskStatus
    submission_id: int | None


class SubmissionOut(BaseModel):
    id: int
    task_id: int
    task_title: str
    child_id: int
    child_name: str
    submitted_by_id: int
    submitted_by_name: str
    status: str
    note: str
    photo_url: str | None
    period_key: str
    submitted_at: datetime
    reviewed_by_id: int | None
    reviewed_at: datetime | None
    review_note: str
    points_awarded: int


class ReviewRequest(BaseModel):
    approve: bool
    note: str = Field(default="", max_length=500)


# ---------------------------------------------------------------------------
# Points
# ---------------------------------------------------------------------------


class TransactionOut(BaseModel):
    id: int
    delta: int
    kind: str
    ref_type: str | None
    ref_id: int | None
    note: str
    created_at: datetime


class PointSummary(BaseModel):
    child_id: int
    balance: int
    available: int
    locked: int
    lifetime_earned: int
    level: int
    level_progress: int
    streak_days: int
    transactions: list[TransactionOut]


class PointAdjustRequest(BaseModel):
    child_id: int
    delta: int
    note: str = Field(min_length=1, max_length=200)

    @field_validator("delta")
    @classmethod
    def delta_not_zero(cls, value: int) -> int:
        if value == 0:
            raise ValueError("调整积分不能为 0")
        return value


# ---------------------------------------------------------------------------
# Rewards, redemptions, savings
# ---------------------------------------------------------------------------


class SavingsLockOut(BaseModel):
    id: int
    reward_id: int
    reward_title: str
    child_name: str
    amount: int
    status: str
    note: str
    created_at: datetime
    released_at: datetime | None


class SavingsLockCreate(BaseModel):
    reward_id: int
    amount: int = Field(gt=0)
    note: str = Field(default="", max_length=200)


class SavingsSummary(BaseModel):
    child_id: int
    locked_total: int
    locks: list[SavingsLockOut]


class RewardCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    emoji: str = Field(default="🎁", max_length=16)
    description: str = ""
    value: float = Field(default=0, ge=0, le=10_000_000)
    unit: RewardUnit = "points"
    multiplier: float = Field(default=1.0, gt=0, le=100)
    stock: int = Field(default=1, ge=-1, le=1_000_000)
    is_long_term: bool = False
    active: bool = True


class RewardUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    emoji: str | None = Field(default=None, max_length=16)
    description: str | None = None
    value: float | None = Field(default=None, ge=0, le=10_000_000)
    unit: RewardUnit | None = None
    multiplier: float | None = Field(default=None, gt=0, le=100)
    stock: int | None = Field(default=None, ge=-1, le=1_000_000)
    is_long_term: bool | None = None
    active: bool | None = None


class RewardOut(BaseModel):
    id: int
    title: str
    emoji: str
    description: str
    value: float
    unit: str
    multiplier: float
    cost_points: int
    stock: int
    is_long_term: bool
    active: bool
    locked_points: int = 0
    progress_percent: int = 0
    remaining_points: int = 0
    estimated_days: int | None = None
    locks: list[SavingsLockOut] = Field(default_factory=list)


class RedemptionCreate(BaseModel):
    reward_id: int


class RedemptionOut(BaseModel):
    id: int
    reward_id: int
    reward_title: str
    reward_emoji: str
    child_id: int
    child_name: str
    cost_points: int
    multiplier_snapshot: float
    status: str
    requested_at: datetime
    reviewed_at: datetime | None
    review_note: str
    fulfilled_at: datetime | None


# ---------------------------------------------------------------------------
# Composite views
# ---------------------------------------------------------------------------


class ChildHome(BaseModel):
    member: MemberOut
    family_name: str
    balance: int
    available: int
    locked: int
    lifetime_earned: int
    level: int
    level_progress: int
    streak_days: int
    today_tasks: list[TodayTaskOut]
    goals: list[GoalOut]
    long_term_rewards: list[RewardOut]
    recent_transactions: list[TransactionOut]
    recent_redemptions: list[RedemptionOut]


class ChildSummary(BaseModel):
    member: MemberOut
    balance: int
    available: int
    locked: int
    week_earned: int
    level: int


class ParentDashboard(BaseModel):
    family_name: str
    children: list[ChildSummary]
    pending_submissions: list[SubmissionOut]
    pending_redemptions: list[RedemptionOut]
    unfulfilled_redemptions: list[RedemptionOut]
    active_locks: list[SavingsLockOut]
    today_tasks: list[TodayTaskOut]


class BackupOut(BaseModel):
    filename: str
    created_at: datetime


class MessageOut(BaseModel):
    message: str
