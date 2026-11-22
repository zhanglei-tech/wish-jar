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
ProgressMode = Literal["points", "task_count"]
WishStatus = Literal["pending", "listed", "rejected"]
MatchSource = Literal["manual", "auto"]
MatchStatus = Literal["active", "used", "voided", "revoked"]


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


class GoalStageIn(BaseModel):
    id: int | None = None
    threshold_value: int = Field(gt=0, le=1_000_000)
    badge_name: str = Field(default="", max_length=100)
    badge_emoji: str = Field(default="", max_length=16)
    badge_image_path: str | None = Field(default=None, max_length=500)


class GoalStageOut(GoalStageIn):
    id: int
    badge_image_url: str | None = None
    sort_order: int
    achieved: bool = False
    badge_awarded: bool = False


class GoalCreate(BaseModel):
    child_id: int
    title: str = Field(min_length=1, max_length=100)
    emoji: str = Field(default="🎯", max_length=16)
    icon_image_path: str | None = Field(default=None, max_length=500)
    description: str = ""
    target_points: int | None = Field(default=None, ge=0, le=1_000_000)
    target_value: int | None = Field(default=None, ge=0, le=1_000_000)
    progress_mode: ProgressMode = "points"
    badge_name: str = Field(default="", max_length=100)
    badge_emoji: str = Field(default="", max_length=16)
    badge_image_path: str | None = Field(default=None, max_length=500)
    start_date: date | None = None
    end_date: date | None = None
    stages: list[GoalStageIn] = Field(default_factory=list, max_length=10)


class GoalUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    emoji: str | None = Field(default=None, max_length=16)
    icon_image_path: str | None = Field(default=None, max_length=500)
    description: str | None = None
    target_points: int | None = Field(default=None, ge=0, le=1_000_000)
    target_value: int | None = Field(default=None, ge=0, le=1_000_000)
    badge_name: str | None = Field(default=None, max_length=100)
    badge_emoji: str | None = Field(default=None, max_length=16)
    badge_image_path: str | None = Field(default=None, max_length=500)
    start_date: date | None = None
    end_date: date | None = None
    status: GoalStatus | None = None
    stages: list[GoalStageIn] | None = Field(default=None, max_length=10)


class GoalOut(BaseModel):
    id: int
    child_id: int
    title: str
    emoji: str
    icon_url: str | None
    description: str
    progress_mode: str
    target_points: int
    target_value: int
    badge_name: str
    badge_emoji: str
    badge_image_url: str | None
    start_date: date | None
    end_date: date | None
    status: str
    completed_at: datetime | None
    earned_points: int
    progress_value: int
    progress_percent: int
    task_count: int
    next_stage: GoalStageOut | None
    stages: list[GoalStageOut]


# ---------------------------------------------------------------------------
# Tasks and submissions
# ---------------------------------------------------------------------------


class TaskCreate(BaseModel):
    child_id: int
    goal_id: int | None = None
    reward_id: int | None = None
    title: str = Field(min_length=1, max_length=100)
    description: str = ""
    points: int = Field(default=0, ge=0, le=10000)
    task_type: TaskType = "daily"
    requires_photo: bool = False
    active_weekdays: list[int] = Field(
        default_factory=lambda: [1, 2, 3, 4, 5, 6, 7],
        min_length=1,
        max_length=7,
    )
    streak_threshold_days: int = Field(default=7, ge=1, le=30)
    streak_bonus_percent: int = Field(default=25, ge=0, le=100)
    active: bool = True

    @field_validator("active_weekdays")
    @classmethod
    def valid_weekdays(cls, value: list[int]) -> list[int]:
        days = sorted(set(value))
        if any(day < 1 or day > 7 for day in days):
            raise ValueError("适用星期必须在 1–7 之间")
        if not days:
            raise ValueError("至少选择一个适用星期")
        return days


class TaskUpdate(BaseModel):
    goal_id: int | None = None
    reward_id: int | None = None
    title: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    points: int | None = Field(default=None, ge=0, le=10000)
    task_type: TaskType | None = None
    requires_photo: bool | None = None
    active_weekdays: list[int] | None = Field(default=None, min_length=1, max_length=7)
    streak_threshold_days: int | None = Field(default=None, ge=1, le=30)
    streak_bonus_percent: int | None = Field(default=None, ge=0, le=100)
    active: bool | None = None

    @field_validator("active_weekdays")
    @classmethod
    def valid_weekdays(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        days = sorted(set(value))
        if any(day < 1 or day > 7 for day in days):
            raise ValueError("适用星期必须在 1–7 之间")
        if not days:
            raise ValueError("至少选择一个适用星期")
        return days


class TaskOut(BaseModel):
    id: int
    child_id: int
    goal_id: int | None
    goal_title: str | None
    reward_id: int | None
    reward_title: str | None
    title: str
    description: str
    points: int
    task_type: str
    requires_photo: bool
    active_weekdays: list[int]
    streak_threshold_days: int
    streak_bonus_percent: int
    streak_days: int = 0
    bonus_active: bool = False
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
    bonus_points: int
    bonus_percent: int


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


class BadgeOut(BaseModel):
    id: int
    kind: str
    level: int | None
    goal_id: int | None
    goal_stage_id: int | None
    goal_title: str | None
    name: str
    emoji: str
    image_url: str | None
    awarded_at: datetime


class LevelThresholdItem(BaseModel):
    level: int = Field(ge=2, le=20)
    required_points: int = Field(ge=0, le=10_000_000)


class LevelThresholdOut(BaseModel):
    level: int
    required_points: int


class LevelConfigOut(BaseModel):
    thresholds: list[LevelThresholdOut]


class LevelConfigUpdate(BaseModel):
    thresholds: list[LevelThresholdItem] = Field(min_length=19, max_length=19)


class PointSummary(BaseModel):
    child_id: int
    balance: int
    available: int
    locked: int
    lifetime_earned: int
    level: int
    level_progress: int
    next_level_points: int
    streak_days: int
    badges: list[BadgeOut]
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
    auto_match_percent: int = Field(default=0, ge=0, le=100)
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
    auto_match_percent: int | None = Field(default=None, ge=0, le=100)
    active: bool | None = None


class WishMatchOut(BaseModel):
    id: int
    reward_id: int
    reward_title: str
    child_id: int
    child_name: str
    parent_name: str
    amount: int
    used_amount: int
    source: str
    status: str
    note: str
    ratio_snapshot: int | None
    redemption_id: int | None
    created_at: datetime
    voided_at: datetime | None


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
    auto_match_percent: int
    active: bool
    locked_points: int = 0
    manual_matched_points: int = 0
    auto_match_points: int = 0
    matched_points: int = 0
    saved_points: int = 0
    progress_percent: int = 0
    remaining_points: int = 0
    estimated_days: int | None = None
    locks: list[SavingsLockOut] = Field(default_factory=list)
    matches: list[WishMatchOut] = Field(default_factory=list)
    linked_tasks: list[TaskOut] = Field(default_factory=list)
    reward_task_points: int = 0
    reward_task_count: int = 0


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


class MatchCreate(BaseModel):
    reward_id: int
    child_id: int
    amount: int = Field(gt=0, le=10_000_000)
    note: str = Field(default="", max_length=200)


# ---------------------------------------------------------------------------
# Wishes
# ---------------------------------------------------------------------------


class WishOut(BaseModel):
    id: int
    child_id: int
    child_name: str
    title: str
    emoji: str
    image_url: str | None
    reason: str
    expected_points: int
    status: str
    reward_id: int | None
    reward_title: str | None
    reject_reason: str
    created_at: datetime
    reviewed_at: datetime | None


class WishRejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=300)


class WishListRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    emoji: str | None = Field(default=None, max_length=16)
    description: str | None = None
    value: float = Field(default=0, ge=0, le=10_000_000)
    unit: RewardUnit = "points"
    multiplier: float = Field(default=1.0, gt=0, le=100)
    stock: int = Field(default=1, ge=-1, le=1_000_000)
    is_long_term: bool = False
    auto_match_percent: int = Field(default=0, ge=0, le=100)


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


class StatsBucket(BaseModel):
    label: str
    task_points: int = 0
    bonus_points: int = 0
    redeemed_points: int = 0
    adjusted_points: int = 0
    net_points: int = 0


class StatsTaskRate(BaseModel):
    approved: int
    expected: int
    percent: int


class StatsOut(BaseModel):
    child_id: int
    child_name: str
    period: str
    label: str
    start_date: date
    end_date: date
    task_points: int
    bonus_points: int
    redeemed_points: int
    adjusted_points: int
    net_points: int
    task_completion: StatsTaskRate
    redemption_count: int
    redemption_points: int
    redemption_statuses: dict[str, int]
    buckets: list[StatsBucket]
    has_data: bool


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
    next_level_points: int
    streak_days: int
    badges: list[BadgeOut]
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
    pending_wish_count: int
    active_locks: list[SavingsLockOut]
    today_tasks: list[TodayTaskOut]


class BackupOut(BaseModel):
    filename: str
    created_at: datetime


class MessageOut(BaseModel):
    message: str
