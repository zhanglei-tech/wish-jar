from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .constants import (
    ALL_WEEKDAYS,
    GOAL_ACTIVE,
    GOAL_PROGRESS_POINTS,
    LOCK_ACTIVE,
    REDEMPTION_PENDING,
    ROLE_CHILD,
    SUBMISSION_PENDING,
    TASK_DAILY,
    WISH_PENDING,
)
from .db import Base
from .timeutils import utcnow


class Family(Base):
    __tablename__ = "families"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(
        ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False, default=ROLE_CHILD)
    avatar: Mapped[str] = mapped_column(String(16), nullable=False, default="🌱")
    pin_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    approval_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(
        ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True
    )
    child_id: Mapped[int] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    emoji: Mapped[str] = mapped_column(String(16), nullable=False, default="🎯")
    icon_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    target_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default=GOAL_PROGRESS_POINTS
    )
    target_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    badge_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    badge_emoji: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    badge_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=GOAL_ACTIVE)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class GoalStage(Base):
    __tablename__ = "goal_stages"
    __table_args__ = (
        UniqueConstraint("goal_id", "sort_order", name="uq_goal_stage_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    goal_id: Mapped[int] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    threshold_value: Mapped[int] = mapped_column(Integer, nullable=False)
    badge_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    badge_emoji: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    badge_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)


class LevelThreshold(Base):
    __tablename__ = "level_thresholds"
    __table_args__ = (
        UniqueConstraint("family_id", "level", name="uq_level_threshold_family"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(
        ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    required_points: Mapped[int] = mapped_column(Integer, nullable=False)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(
        ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True
    )
    child_id: Mapped[int] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    goal_id: Mapped[int | None] = mapped_column(
        ForeignKey("goals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    reward_id: Mapped[int | None] = mapped_column(
        ForeignKey("rewards.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    task_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TASK_DAILY
    )
    requires_photo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    active_weekdays: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ALL_WEEKDAYS
    )
    streak_threshold_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=7
    )
    streak_bonus_percent: Mapped[int] = mapped_column(
        Integer, nullable=False, default=25
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint("task_id", "period_key", name="uq_submission_task_period"),
        Index("ix_submissions_child_status", "child_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    child_id: Mapped[int] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    submitted_by_id: Mapped[int] = mapped_column(
        ForeignKey("members.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SUBMISSION_PENDING
    )
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    period_key: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    reviewed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("members.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    points_awarded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bonus_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bonus_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PointTransaction(Base):
    __tablename__ = "point_transactions"
    __table_args__ = (
        Index("ix_point_transactions_child_created", "child_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(
        ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True
    )
    child_id: Mapped[int] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    ref_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class Reward(Base):
    __tablename__ = "rewards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(
        ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    emoji: Mapped[str] = mapped_column(String(16), nullable=False, default="🎁")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    value: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="points")
    multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    cost_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_long_term: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    auto_match_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class ChildBadge(Base):
    __tablename__ = "child_badges"
    __table_args__ = (
        UniqueConstraint("child_id", "kind", "level", name="uq_child_badge_level"),
        UniqueConstraint(
            "child_id", "goal_stage_id", name="uq_child_badge_stage"
        ),
        Index("ix_child_badges_child_awarded", "child_id", "awarded_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(
        ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True
    )
    child_id: Mapped[int] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    goal_id: Mapped[int | None] = mapped_column(
        ForeignKey("goals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    goal_stage_id: Mapped[int | None] = mapped_column(
        ForeignKey("goal_stages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    emoji: Mapped[str] = mapped_column(String(16), nullable=False, default="🏅")
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    awarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class Wish(Base):
    __tablename__ = "wishes"
    __table_args__ = (
        Index("ix_wishes_child_status", "child_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(
        ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True
    )
    child_id: Mapped[int] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    emoji: Mapped[str] = mapped_column(String(16), nullable=False, default="🌟")
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    expected_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=WISH_PENDING)
    reward_id: Mapped[int | None] = mapped_column(
        ForeignKey("rewards.id", ondelete="SET NULL"), nullable=True
    )
    reject_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reviewed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("members.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class WishMatch(Base):
    __tablename__ = "wish_matches"
    __table_args__ = (
        Index("ix_wish_matches_reward_status", "reward_id", "status"),
        Index("ix_wish_matches_child_status", "child_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(
        ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True
    )
    child_id: Mapped[int] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reward_id: Mapped[int] = mapped_column(
        ForeignKey("rewards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("members.id"), nullable=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    used_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ratio_snapshot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    redemption_id: Mapped[int | None] = mapped_column(
        ForeignKey("redemptions.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    voided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Redemption(Base):
    __tablename__ = "redemptions"
    __table_args__ = (
        Index("ix_redemptions_child_status", "child_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reward_id: Mapped[int] = mapped_column(
        ForeignKey("rewards.id"), nullable=False, index=True
    )
    child_id: Mapped[int] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cost_points: Mapped[int] = mapped_column(Integer, nullable=False)
    multiplier_snapshot: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=REDEMPTION_PENDING
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    reviewed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("members.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    fulfilled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class SavingsLock(Base):
    __tablename__ = "savings_locks"
    __table_args__ = (
        Index("ix_savings_locks_child_status", "child_id", "status"),
        Index("ix_savings_locks_reward_status", "reward_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(
        ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True
    )
    child_id: Mapped[int] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reward_id: Mapped[int] = mapped_column(
        ForeignKey("rewards.id"), nullable=False, index=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=LOCK_ACTIVE
    )
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    released_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("members.id"), nullable=True
    )
