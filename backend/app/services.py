import math
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .config import Settings
from .constants import (
    BADGE_ACHIEVEMENT,
    BADGE_LEVEL,
    GOAL_COMPLETED,
    GOAL_PROGRESS_POINTS,
    GOAL_PROGRESS_TASK_COUNT,
    LOCK_ACTIVE,
    LOCK_REDEEMED,
    LOCK_RELEASED,
    MATCH_ACTIVE,
    MATCH_AUTO,
    MATCH_MANUAL,
    MATCH_REVOKED,
    MATCH_USED,
    MATCH_VOIDED,
    MAX_LEVEL,
    REDEMPTION_APPROVED,
    REDEMPTION_FULFILLED,
    REDEMPTION_PENDING,
    REDEMPTION_REJECTED,
    ROLE_CHILD,
    ROLE_PARENT,
    SUBMISSION_APPROVED,
    SUBMISSION_PENDING,
    SUBMISSION_REJECTED,
    TASK_DAILY,
    WISH_LISTED,
    WISH_PENDING,
    WISH_REJECTED,
)
from .models import (
    ChildBadge,
    Family,
    Goal,
    GoalStage,
    LevelThreshold,
    Member,
    PointTransaction,
    Redemption,
    Reward,
    SavingsLock,
    Submission,
    Task,
    Wish,
    WishMatch,
)
from .schemas import (
    BadgeOut,
    ChildHome,
    ChildSummary,
    GoalOut,
    GoalStageOut,
    MemberOut,
    ParentDashboard,
    PointSummary,
    RedemptionOut,
    RewardOut,
    SavingsLockOut,
    StatsBucket,
    StatsOut,
    StatsTaskRate,
    SubmissionOut,
    TaskOut,
    TodayTaskOut,
    TransactionOut,
    WishMatchOut,
    WishOut,
)
from .timeutils import (
    as_utc,
    bucket_starts,
    local_date_end_utc,
    local_date_start_utc,
    local_today,
    period_bounds,
    period_key,
    to_local,
    utcnow,
    week_start_utc,
)

DEFAULT_LEVEL_STEP = 100
# 与 frontend/src/levels.ts 的 LEVEL_NAMES 保持一致。
LEVEL_BADGE_NAMES = {
    1: "初心",
    2: "初芽",
    3: "新叶",
    4: "嫩枝",
    5: "青枝",
    6: "小树",
    7: "繁叶",
    8: "含苞",
    9: "初绽",
    10: "盛放",
    11: "初果",
    12: "双果",
    13: "丰果",
    14: "晶叶",
    15: "晶枝",
    16: "晶树",
    17: "星辉",
    18: "星河",
    19: "星域",
    20: "星辉王冠",
}
LEVEL_BADGE_EMOJI = {
    range(2, 5): "🌱",
    range(5, 8): "🌿",
    range(8, 11): "🥉",
    range(11, 14): "🥈",
    range(14, 17): "🥇",
    range(17, 20): "💎",
    range(20, 21): "👑",
}


def media_url(path: str | None) -> str | None:
    if not path:
        return None
    name = Path(path).name
    return f"/api/media/{name}" if name else None


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def serialize_member(member: Member) -> MemberOut:
    return MemberOut(
        id=member.id,
        name=member.name,
        avatar=member.avatar,
        role=member.role,
        approval_required=member.approval_required,
        is_active=member.is_active,
    )


def get_family_name(db: Session, family_id: int) -> str:
    family = db.get(Family, family_id)
    return family.name if family else ""


def serialize_transaction(transaction: PointTransaction) -> TransactionOut:
    return TransactionOut(
        id=transaction.id,
        delta=transaction.delta,
        kind=transaction.kind,
        ref_type=transaction.ref_type,
        ref_id=transaction.ref_id,
        note=transaction.note,
        created_at=transaction.created_at,
    )


def serialize_lock(db: Session, lock: SavingsLock) -> SavingsLockOut:
    reward = db.get(Reward, lock.reward_id)
    child = db.get(Member, lock.child_id)
    return SavingsLockOut(
        id=lock.id,
        reward_id=lock.reward_id,
        reward_title=reward.title if reward else "已删除的心愿",
        child_name=child.name if child else "",
        amount=lock.amount,
        status=lock.status,
        note=lock.note,
        created_at=lock.created_at,
        released_at=lock.released_at,
    )


def _goal_progress(db: Session, goal: Goal) -> tuple[int, int]:
    """Return (progress_value, approved_submission_count)."""
    row = db.execute(
        select(
            func.coalesce(func.sum(Submission.points_awarded), 0),
            func.coalesce(func.sum(Submission.bonus_points), 0),
            func.count(Submission.id),
        )
        .select_from(Submission)
        .join(Task, Task.id == Submission.task_id)
        .where(
            Task.goal_id == goal.id,
            Submission.status == SUBMISSION_APPROVED,
        )
    ).one()
    points = int(row[0] or 0) + int(row[1] or 0)
    count = int(row[2] or 0)
    if goal.progress_mode == GOAL_PROGRESS_TASK_COUNT:
        return count, count
    return points, count


def serialize_goal(db: Session, goal: Goal) -> GoalOut:
    progress_value, task_count = _goal_progress(db, goal)
    earned = progress_value if goal.progress_mode == GOAL_PROGRESS_POINTS else 0
    target = goal.target_value if goal.target_value else goal.target_points
    progress = (
        min(100, round(progress_value * 100 / target)) if target > 0 else 0
    )
    awarded_stage_ids = set(
        db.scalars(
            select(ChildBadge.goal_stage_id).where(
                ChildBadge.child_id == goal.child_id,
                ChildBadge.goal_stage_id.is_not(None),
            )
        ).all()
    )
    stages = db.scalars(
        select(GoalStage)
        .where(GoalStage.goal_id == goal.id)
        .order_by(GoalStage.sort_order)
    ).all()
    stage_out = [
        GoalStageOut(
            id=stage.id,
            threshold_value=stage.threshold_value,
            badge_name=stage.badge_name or f"{goal.title} · {stage.threshold_value}",
            badge_emoji=stage.badge_emoji or goal.badge_emoji or goal.emoji,
            badge_image_path=stage.badge_image_path,
            badge_image_url=media_url(stage.badge_image_path),
            sort_order=stage.sort_order,
            achieved=progress_value >= stage.threshold_value,
            badge_awarded=stage.id in awarded_stage_ids,
        )
        for stage in stages
    ]
    next_stage = next(
        (stage for stage in stage_out if not stage.achieved), None
    )
    return GoalOut(
        id=goal.id,
        child_id=goal.child_id,
        title=goal.title,
        emoji=goal.emoji,
        icon_url=media_url(goal.icon_image_path),
        description=goal.description,
        progress_mode=goal.progress_mode,
        target_points=target if goal.progress_mode == GOAL_PROGRESS_POINTS else 0,
        target_value=target,
        badge_name=goal.badge_name or goal.title,
        badge_emoji=goal.badge_emoji or goal.emoji,
        badge_image_url=media_url(goal.badge_image_path),
        start_date=goal.start_date,
        end_date=goal.end_date,
        status=goal.status,
        completed_at=goal.completed_at,
        earned_points=earned,
        progress_value=progress_value,
        progress_percent=progress,
        task_count=task_count,
        next_stage=next_stage,
        stages=stage_out,
    )


def parse_weekdays(value: str | None) -> list[int]:
    if not value:
        return [1, 2, 3, 4, 5, 6, 7]
    days = sorted({int(part) for part in value.split(",") if part.strip()})
    return [day for day in days if 1 <= day <= 7] or [1, 2, 3, 4, 5, 6, 7]


def weekdays_to_string(days: list[int]) -> str:
    return ",".join(str(day) for day in sorted(set(days)))


def task_applies_on(task: Task, value: date) -> bool:
    return value.isoweekday() in parse_weekdays(task.active_weekdays)


def task_streak_days(
    db: Session, task: Task, settings: Settings, upto: date | None = None
) -> int:
    if task.task_type != TASK_DAILY:
        return 0
    rows = db.scalars(
        select(Submission.submitted_at).where(
            Submission.task_id == task.id,
            Submission.status == SUBMISSION_APPROVED,
        )
    ).all()
    earned = {to_local(row, settings).date() for row in rows if row is not None}
    if not earned:
        return 0
    cursor = upto or local_today(settings)
    if cursor not in earned:
        # Today may not be over yet; count the most recent applicable run.
        if task_applies_on(task, cursor):
            return 0
        while cursor not in earned and cursor >= min(earned):
            cursor -= timedelta(days=1)
            if task_applies_on(task, cursor) and cursor in earned:
                break
    created = to_local(task.created_at, settings).date()
    count = 0
    guard = 0
    while cursor >= created and guard < 4000:
        guard += 1
        if task_applies_on(task, cursor):
            if cursor in earned:
                count += 1
                cursor -= timedelta(days=1)
            else:
                break
        else:
            cursor -= timedelta(days=1)
    return count


def serialize_task(db: Session, task: Task, settings: Settings | None = None) -> TaskOut:
    goal = db.get(Goal, task.goal_id) if task.goal_id else None
    reward = db.get(Reward, task.reward_id) if task.reward_id else None
    streak = task_streak_days(db, task, settings) if settings else 0
    return TaskOut(
        id=task.id,
        child_id=task.child_id,
        goal_id=task.goal_id,
        goal_title=goal.title if goal else None,
        reward_id=task.reward_id,
        reward_title=reward.title if reward else None,
        title=task.title,
        description=task.description,
        points=task.points,
        task_type=task.task_type,
        requires_photo=task.requires_photo,
        active_weekdays=parse_weekdays(task.active_weekdays),
        streak_threshold_days=task.streak_threshold_days,
        streak_bonus_percent=task.streak_bonus_percent,
        streak_days=streak,
        bonus_active=(
            task.task_type == TASK_DAILY
            and task.streak_bonus_percent > 0
            and streak >= task.streak_threshold_days
        ),
        active=task.active,
    )


def serialize_submission(db: Session, submission: Submission) -> SubmissionOut:
    task = db.get(Task, submission.task_id)
    child = db.get(Member, submission.child_id)
    submitter = db.get(Member, submission.submitted_by_id)
    return SubmissionOut(
        id=submission.id,
        task_id=submission.task_id,
        task_title=task.title if task else "已删除任务",
        child_id=submission.child_id,
        child_name=child.name if child else "",
        submitted_by_id=submission.submitted_by_id,
        submitted_by_name=submitter.name if submitter else "",
        status=submission.status,
        note=submission.note,
        photo_url=submission.photo_path,
        period_key=submission.period_key,
        submitted_at=submission.submitted_at,
        reviewed_by_id=submission.reviewed_by_id,
        reviewed_at=submission.reviewed_at,
        review_note=submission.review_note,
        points_awarded=submission.points_awarded,
        bonus_points=submission.bonus_points,
        bonus_percent=submission.bonus_percent,
    )


def serialize_redemption(db: Session, redemption: Redemption) -> RedemptionOut:
    reward = db.get(Reward, redemption.reward_id)
    child = db.get(Member, redemption.child_id)
    return RedemptionOut(
        id=redemption.id,
        reward_id=redemption.reward_id,
        reward_title=reward.title if reward else "已删除的奖励",
        reward_emoji=reward.emoji if reward else "🎁",
        child_id=redemption.child_id,
        child_name=child.name if child else "",
        cost_points=redemption.cost_points,
        multiplier_snapshot=redemption.multiplier_snapshot,
        status=redemption.status,
        requested_at=redemption.requested_at,
        reviewed_at=redemption.reviewed_at,
        review_note=redemption.review_note,
        fulfilled_at=redemption.fulfilled_at,
    )


# ---------------------------------------------------------------------------
# Point and progress calculations
# ---------------------------------------------------------------------------


def get_balance(db: Session, child_id: int) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(PointTransaction.delta), 0)).where(
                PointTransaction.child_id == child_id
            )
        )
        or 0
    )


def get_locked_total(
    db: Session, child_id: int, reward_id: int | None = None
) -> int:
    stmt = select(func.coalesce(func.sum(SavingsLock.amount), 0)).where(
        SavingsLock.child_id == child_id,
        SavingsLock.status == LOCK_ACTIVE,
    )
    if reward_id is not None:
        stmt = stmt.where(SavingsLock.reward_id == reward_id)
    return int(db.scalar(stmt) or 0)


def get_available(db: Session, child_id: int) -> int:
    return get_balance(db, child_id) - get_locked_total(db, child_id)


def get_lifetime_earned(db: Session, child_id: int) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(PointTransaction.delta), 0)).where(
                PointTransaction.child_id == child_id,
                PointTransaction.kind.in_(("task", "streak_bonus")),
                PointTransaction.delta > 0,
            )
        )
        or 0
    )


def get_level_thresholds(db: Session, family_id: int) -> dict[int, int]:
    rows = db.scalars(
        select(LevelThreshold).where(LevelThreshold.family_id == family_id)
    ).all()
    configured = {row.level: row.required_points for row in rows}
    thresholds = {1: 0}
    previous = 0
    for level in range(2, MAX_LEVEL + 1):
        value = configured.get(level, DEFAULT_LEVEL_STEP * (level - 1))
        value = max(value, previous + 1)
        thresholds[level] = value
        previous = value
    return thresholds


def level_info(db: Session, family_id: int, lifetime: int) -> tuple[int, int, int]:
    thresholds = get_level_thresholds(db, family_id)
    level = 1
    for candidate in range(2, MAX_LEVEL + 1):
        if lifetime >= thresholds[candidate]:
            level = candidate
        else:
            break
    next_points = 0
    if level < MAX_LEVEL:
        next_points = max(thresholds[level + 1] - lifetime, 0)
    progress = max(lifetime - thresholds[level], 0)
    return level, progress, next_points


def level_badge_name(level: int) -> str:
    return LEVEL_BADGE_NAMES.get(level, f"Lv.{level} 徽章")


def level_badge_emoji(level: int) -> str:
    for span, emoji in LEVEL_BADGE_EMOJI.items():
        if level in span:
            return emoji
    return "🏅"


def serialize_badge(db: Session, badge: ChildBadge) -> BadgeOut:
    goal = db.get(Goal, badge.goal_id) if badge.goal_id else None
    return BadgeOut(
        id=badge.id,
        kind=badge.kind,
        level=badge.level,
        goal_id=badge.goal_id,
        goal_stage_id=badge.goal_stage_id,
        goal_title=goal.title if goal else None,
        name=(
            level_badge_name(badge.level)
            if badge.kind == BADGE_LEVEL and badge.level is not None
            else badge.name
        ),
        emoji=badge.emoji,
        image_url=media_url(badge.image_path),
        awarded_at=badge.awarded_at,
    )


def get_badges(db: Session, child_id: int) -> list[ChildBadge]:
    return list(
        db.scalars(
            select(ChildBadge)
            .where(ChildBadge.child_id == child_id)
            .order_by(ChildBadge.awarded_at.desc(), ChildBadge.id.desc())
        ).all()
    )


def _award_level_badges(db: Session, child: Member, lifetime: int) -> None:
    level, _, _ = level_info(db, child.family_id, lifetime)
    existing = set(
        db.scalars(
            select(ChildBadge.level).where(
                ChildBadge.child_id == child.id,
                ChildBadge.kind == BADGE_LEVEL,
            )
        ).all()
    )
    for value in range(2, level + 1):
        if value in existing:
            continue
        db.add(
            ChildBadge(
                family_id=child.family_id,
                child_id=child.id,
                kind=BADGE_LEVEL,
                level=value,
                name=level_badge_name(value),
                emoji=level_badge_emoji(value),
            )
        )
    db.flush()


def sync_level_badges(db: Session, child: Member) -> None:
    _award_level_badges(db, child, get_lifetime_earned(db, child.id))


def _copy_badge_image(
    source: str | None, settings: Settings, prefix: str
) -> str | None:
    if not source:
        return None
    name = Path(source).name
    if not name:
        return None
    source_path = Path(settings.upload_dir) / name
    if not source_path.is_file():
        return None
    suffix = source_path.suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        return None
    target_name = f"{prefix}-{int(utcnow().timestamp())}-{name}"
    target = Path(settings.upload_dir) / target_name
    try:
        shutil.copy2(source_path, target)
    except OSError:
        return None
    return f"/uploads/{target_name}"


def _award_goal_badge(
    db: Session,
    goal: Goal,
    stage: GoalStage | None,
    settings: Settings | None,
) -> None:
    if stage is None:
        exists = db.scalar(
            select(ChildBadge.id).where(
                ChildBadge.child_id == goal.child_id,
                ChildBadge.goal_id == goal.id,
                ChildBadge.goal_stage_id.is_(None),
            )
        )
        if exists is not None:
            return
        image_path = (
            _copy_badge_image(goal.badge_image_path, settings, "achievement")
            if settings
            else goal.badge_image_path
        )
        db.add(
            ChildBadge(
                family_id=goal.family_id,
                child_id=goal.child_id,
                kind=BADGE_ACHIEVEMENT,
                goal_id=goal.id,
                name=goal.badge_name or f"{goal.title} · 完成",
                emoji=goal.badge_emoji or goal.emoji,
                image_path=image_path,
            )
        )
    else:
        exists = db.scalar(
            select(ChildBadge.id).where(
                ChildBadge.child_id == goal.child_id,
                ChildBadge.goal_stage_id == stage.id,
            )
        )
        if exists is not None:
            return
        image_path = (
            _copy_badge_image(stage.badge_image_path, settings, "stage")
            if settings
            else stage.badge_image_path
        )
        db.add(
            ChildBadge(
                family_id=goal.family_id,
                child_id=goal.child_id,
                kind=BADGE_ACHIEVEMENT,
                goal_id=goal.id,
                goal_stage_id=stage.id,
                name=stage.badge_name or f"{goal.title} · {stage.threshold_value}",
                emoji=stage.badge_emoji or goal.badge_emoji or goal.emoji,
                image_path=image_path,
            )
        )
    db.flush()


def sync_goal_awards(
    db: Session,
    goal: Goal,
    settings: Settings | None = None,
    manual_complete: bool = False,
) -> None:
    if manual_complete:
        if goal.completed_at is None:
            goal.completed_at = utcnow()
        if goal.status != GOAL_COMPLETED:
            goal.status = GOAL_COMPLETED
        _award_goal_badge(db, goal, None, settings)
        return

    progress, _ = _goal_progress(db, goal)
    target = goal.target_value or goal.target_points
    if goal.status != GOAL_COMPLETED and target > 0 and progress >= target:
        goal.status = GOAL_COMPLETED
        goal.completed_at = goal.completed_at or utcnow()
        _award_goal_badge(db, goal, None, settings)
        stages = db.scalars(
            select(GoalStage)
            .where(GoalStage.goal_id == goal.id)
            .order_by(GoalStage.sort_order)
        ).all()
        for stage in stages:
            if stage.threshold_value <= progress:
                _award_goal_badge(db, goal, stage, settings)
        return
    if goal.status != GOAL_COMPLETED:
        stages = db.scalars(
            select(GoalStage)
            .where(GoalStage.goal_id == goal.id)
            .order_by(GoalStage.sort_order)
        ).all()
        for stage in stages:
            if stage.threshold_value <= progress:
                _award_goal_badge(db, goal, stage, settings)


def get_streak_days(db: Session, child_id: int, settings: Settings) -> int:
    rows = db.scalars(
        select(Submission.submitted_at).where(
            Submission.child_id == child_id,
            Submission.status == SUBMISSION_APPROVED,
        )
    ).all()
    earned_dates = {to_local(row, settings).date() for row in rows if row}
    if not earned_dates:
        return 0
    cursor = local_today(settings)
    if cursor not in earned_dates:
        cursor = cursor - timedelta(days=1)
    count = 0
    while cursor in earned_dates:
        count += 1
        cursor = cursor - timedelta(days=1)
    return count


def estimate_days(
    db: Session,
    child_id: int,
    remaining_points: int,
    is_long_term: bool,
    settings: Settings,
) -> int | None:
    if remaining_points <= 0:
        return 0
    window_days = 30 if is_long_term else 14
    cutoff = utcnow() - timedelta(days=window_days)
    rows = db.execute(
        select(PointTransaction.delta, PointTransaction.created_at).where(
            PointTransaction.child_id == child_id,
            PointTransaction.kind.in_(("task", "streak_bonus")),
            PointTransaction.delta > 0,
            PointTransaction.created_at >= cutoff,
        )
    ).all()
    if not rows:
        return None
    total = sum(int(row[0]) for row in rows)
    earned_dates = {
        to_local(row[1], settings).date() for row in rows if row[1] is not None
    }
    if total <= 0 or len(earned_dates) < 3:
        return None
    average = total / window_days
    if average <= 0:
        return None
    return max(1, math.ceil(remaining_points / average))


def get_week_earned(db: Session, child_id: int, settings: Settings) -> int:
    start = week_start_utc(settings)
    return int(
        db.scalar(
            select(func.coalesce(func.sum(PointTransaction.delta), 0)).where(
                PointTransaction.child_id == child_id,
                PointTransaction.kind.in_(("task", "streak_bonus")),
                PointTransaction.delta > 0,
                PointTransaction.created_at >= start,
            )
        )
        or 0
    )


def serialize_match(db: Session, match: WishMatch) -> WishMatchOut:
    reward = db.get(Reward, match.reward_id)
    child = db.get(Member, match.child_id)
    parent = db.get(Member, match.parent_id) if match.parent_id else None
    return WishMatchOut(
        id=match.id,
        reward_id=match.reward_id,
        reward_title=reward.title if reward else "已删除的心愿",
        child_id=match.child_id,
        child_name=child.name if child else "",
        parent_name=parent.name if parent else "",
        amount=match.amount,
        used_amount=match.used_amount,
        source=match.source,
        status=match.status,
        note=match.note,
        ratio_snapshot=match.ratio_snapshot,
        redemption_id=match.redemption_id,
        created_at=match.created_at,
        voided_at=match.voided_at,
    )


def get_manual_match_total(
    db: Session, child_id: int | None, reward_id: int
) -> int:
    if not child_id:
        return 0
    return int(
        db.scalar(
            select(func.coalesce(func.sum(WishMatch.amount), 0)).where(
                WishMatch.child_id == child_id,
                WishMatch.reward_id == reward_id,
                WishMatch.source == MATCH_MANUAL,
                WishMatch.status == MATCH_ACTIVE,
            )
        )
        or 0
    )


def calculate_auto_match(
    cost: int, locked: int, manual: int, percent: int
) -> int:
    if percent <= 0 or locked <= 0 or cost <= 0:
        return 0
    room = max(0, cost - locked - manual)
    return min(int(math.floor(locked * percent / 100)), room)


def get_match_pool(
    db: Session, child_id: int, reward: Reward
) -> tuple[int, int, int]:
    locked = get_locked_total(db, child_id, reward.id)
    manual = get_manual_match_total(db, child_id, reward.id)
    auto = calculate_auto_match(
        reward.cost_points, locked, manual, reward.auto_match_percent
    )
    return manual, auto, manual + auto


def get_reward_task_progress(
    db: Session, reward: Reward
) -> tuple[list[Task], int, int]:
    tasks = list(
        db.scalars(
            select(Task)
            .where(Task.reward_id == reward.id)
            .order_by(Task.created_at)
        ).all()
    )
    points = 0
    count = 0
    if tasks:
        task_ids = [task.id for task in tasks]
        row = db.execute(
            select(
                func.coalesce(func.sum(Submission.points_awarded), 0),
                func.coalesce(func.sum(Submission.bonus_points), 0),
                func.count(Submission.id),
            ).where(
                Submission.task_id.in_(task_ids),
                Submission.status == SUBMISSION_APPROVED,
            )
        ).one()
        points = int(row[0] or 0) + int(row[1] or 0)
        count = int(row[2] or 0)
    return tasks, points, count


def serialize_reward(
    db: Session,
    reward: Reward,
    child_id: int | None,
    settings: Settings,
    include_locks: bool = False,
) -> RewardOut:
    locked = get_locked_total(db, child_id, reward.id) if child_id else 0
    cost = reward.cost_points
    manual = get_manual_match_total(db, child_id, reward.id)
    auto = calculate_auto_match(cost, locked, manual, reward.auto_match_percent)
    matched = manual + auto
    saved = locked + matched
    progress = (
        min(100, round(saved * 100 / cost))
        if cost > 0
        else (100 if saved > 0 else 0)
    )
    remaining = max(cost - saved, 0)
    estimated = (
        estimate_days(db, child_id, remaining, reward.is_long_term, settings)
        if child_id
        else None
    )
    locks: list[SavingsLockOut] = []
    matches: list[WishMatchOut] = []
    if include_locks and child_id:
        rows = db.scalars(
            select(SavingsLock)
            .where(
                SavingsLock.child_id == child_id,
                SavingsLock.reward_id == reward.id,
                SavingsLock.status == LOCK_ACTIVE,
            )
            .order_by(SavingsLock.created_at.desc())
        ).all()
        locks = [serialize_lock(db, row) for row in rows]
        match_rows = db.scalars(
            select(WishMatch)
            .where(
                WishMatch.child_id == child_id,
                WishMatch.reward_id == reward.id,
                WishMatch.status.in_((MATCH_ACTIVE, MATCH_USED)),
            )
            .order_by(WishMatch.created_at.desc())
        ).all()
        matches = [serialize_match(db, row) for row in match_rows]
    linked_tasks, task_points, task_count = get_reward_task_progress(db, reward)
    return RewardOut(
        id=reward.id,
        title=reward.title,
        emoji=reward.emoji,
        description=reward.description,
        value=reward.value,
        unit=reward.unit,
        multiplier=reward.multiplier,
        cost_points=reward.cost_points,
        stock=reward.stock,
        is_long_term=reward.is_long_term,
        auto_match_percent=reward.auto_match_percent,
        active=reward.active,
        locked_points=locked,
        manual_matched_points=manual,
        auto_match_points=auto,
        matched_points=matched,
        saved_points=saved,
        progress_percent=progress,
        remaining_points=remaining,
        estimated_days=estimated,
        locks=locks,
        matches=matches,
        linked_tasks=[
            serialize_task(db, task, settings) for task in linked_tasks
        ],
        reward_task_points=task_points,
        reward_task_count=task_count,
    )


def calculate_cost(value: float, multiplier: float) -> int:
    return max(0, math.ceil(value * multiplier))


# ---------------------------------------------------------------------------
# Task submissions and review
# ---------------------------------------------------------------------------


def _create_transaction(
    db: Session,
    family_id: int,
    child_id: int,
    delta: int,
    kind: str,
    note: str,
    ref_type: str | None = None,
    ref_id: int | None = None,
) -> PointTransaction:
    transaction = PointTransaction(
        family_id=family_id,
        child_id=child_id,
        delta=delta,
        kind=kind,
        note=note,
        ref_type=ref_type,
        ref_id=ref_id,
    )
    db.add(transaction)
    return transaction


def _approve_submission(
    db: Session,
    submission: Submission,
    task: Task,
    reviewer: Member,
    settings: Settings,
    note: str = "",
) -> None:
    submission.status = SUBMISSION_APPROVED
    submission.reviewed_by_id = reviewer.id
    submission.reviewed_at = utcnow()
    submission.review_note = note
    submission.points_awarded = task.points
    submission.bonus_points = 0
    submission.bonus_percent = 0
    _create_transaction(
        db,
        family_id=task.family_id,
        child_id=task.child_id,
        delta=task.points,
        kind="task",
        note=f"完成任务：{task.title}",
        ref_type="submission",
        ref_id=submission.id,
    )

    db.flush()
    submitted_local_date = to_local(submission.submitted_at, settings).date()
    streak = task_streak_days(db, task, settings, upto=submitted_local_date)
    if (
        task.task_type == TASK_DAILY
        and task.streak_bonus_percent > 0
        and streak >= task.streak_threshold_days
    ):
        bonus = math.ceil(task.points * task.streak_bonus_percent / 100)
        if bonus > 0:
            submission.bonus_points = bonus
            submission.bonus_percent = task.streak_bonus_percent
            _create_transaction(
                db,
                family_id=task.family_id,
                child_id=task.child_id,
                delta=bonus,
                kind="streak_bonus",
                note=f"连续完成奖励：{task.title}（{streak} 天）",
                ref_type="submission",
                ref_id=submission.id,
            )

    db.flush()
    child = db.get(Member, task.child_id)
    if child is not None:
        _award_level_badges(db, child, get_lifetime_earned(db, child.id))
    if task.goal_id:
        goal = db.get(Goal, task.goal_id)
        if goal is not None:
            sync_goal_awards(db, goal, settings)


def submit_task(
    db: Session,
    task: Task,
    submitter: Member,
    note: str,
    photo_path: str | None,
    settings: Settings,
) -> Submission:
    if not task.active:
        raise ValueError("任务已停用")
    if task.requires_photo and not photo_path:
        raise ValueError("该任务需要上传照片")
    if not task_applies_on(task, local_today(settings)):
        raise ValueError("今天不是这个任务的适用日")
    child = db.get(Member, task.child_id)
    if child is None or child.family_id != task.family_id or not child.is_active:
        raise ValueError("任务所属孩子不可用")

    key = period_key(task.task_type, settings)
    existing = db.scalar(
        select(Submission).where(
            Submission.task_id == task.id,
            Submission.period_key == key,
        )
    )
    if existing is not None:
        if existing.status != SUBMISSION_REJECTED:
            raise ValueError("该任务本周期已提交")
        existing.status = SUBMISSION_PENDING
        existing.note = note
        existing.photo_path = photo_path
        existing.submitted_at = utcnow()
        existing.submitted_by_id = submitter.id
        existing.reviewed_by_id = None
        existing.reviewed_at = None
        existing.review_note = ""
        existing.points_awarded = 0
        existing.bonus_points = 0
        existing.bonus_percent = 0
        submission = existing
    else:
        submission = Submission(
            task_id=task.id,
            child_id=task.child_id,
            submitted_by_id=submitter.id,
            status=SUBMISSION_PENDING,
            note=note,
            photo_path=photo_path,
            period_key=key,
            submitted_at=utcnow(),
        )
        db.add(submission)
        db.flush()

    auto_approve = submitter.role == ROLE_PARENT or not child.approval_required
    if auto_approve:
        _approve_submission(db, submission, task, submitter, settings)
    return submission


def review_submission(
    db: Session,
    submission: Submission,
    reviewer: Member,
    approve: bool,
    note: str,
    settings: Settings,
) -> Submission:
    if submission.status != SUBMISSION_PENDING:
        raise ValueError("该提交已经审核过")
    task = db.get(Task, submission.task_id)
    if task is None:
        raise ValueError("任务不存在")
    if approve:
        _approve_submission(db, submission, task, reviewer, settings, note)
    else:
        submission.status = SUBMISSION_REJECTED
        submission.reviewed_by_id = reviewer.id
        submission.reviewed_at = utcnow()
        submission.review_note = note
        submission.points_awarded = 0
        submission.bonus_points = 0
        submission.bonus_percent = 0
    return submission


# ---------------------------------------------------------------------------
# Point adjustment
# ---------------------------------------------------------------------------


def adjust_points(
    db: Session,
    child: Member,
    delta: int,
    note: str,
) -> PointTransaction:
    if not note.strip():
        raise ValueError("备注不能为空")
    if delta == 0:
        raise ValueError("调整积分不能为 0")
    balance = get_balance(db, child.id)
    locked = get_locked_total(db, child.id)
    new_balance = balance + delta
    if new_balance < 0:
        raise ValueError("调整后余额不能为负")
    if new_balance < locked:
        raise ValueError("调整后余额不能低于已锁定积分")
    return _create_transaction(
        db,
        family_id=child.family_id,
        child_id=child.id,
        delta=delta,
        kind="adjust",
        note=note.strip(),
    )


# ---------------------------------------------------------------------------
# Rewards, redemptions and savings locks
# ---------------------------------------------------------------------------


def create_redemption(
    db: Session, child: Member, reward: Reward
) -> Redemption:
    if not reward.active:
        raise ValueError("奖励已下架")
    if reward.stock == 0:
        raise ValueError("该奖励已兑完")
    cost = reward.cost_points
    available = get_available(db, child.id)
    locked = get_locked_total(db, child.id, reward.id)
    _, _, pool = get_match_pool(db, child.id, reward)
    if available + locked + pool < cost:
        raise ValueError("可用积分不足")
    redemption = Redemption(
        reward_id=reward.id,
        child_id=child.id,
        cost_points=cost,
        multiplier_snapshot=reward.multiplier,
        status=REDEMPTION_PENDING,
        requested_at=utcnow(),
    )
    db.add(redemption)
    db.flush()
    return redemption


def review_redemption(
    db: Session,
    redemption: Redemption,
    reviewer: Member,
    approve: bool,
    note: str,
) -> Redemption:
    if redemption.status != REDEMPTION_PENDING:
        raise ValueError("该兑换申请已经处理过")
    if not approve:
        redemption.status = REDEMPTION_REJECTED
        redemption.reviewed_by_id = reviewer.id
        redemption.reviewed_at = utcnow()
        redemption.review_note = note
        return redemption

    reward = db.get(Reward, redemption.reward_id)
    child = db.get(Member, redemption.child_id)
    if reward is None or child is None:
        raise ValueError("奖励或孩子不存在")
    if reward.stock == 0:
        raise ValueError("该奖励已兑完")
    cost = redemption.cost_points
    balance = get_balance(db, child.id)
    locked = get_locked_total(db, child.id, reward.id)
    manual_matches = list(
        db.scalars(
            select(WishMatch)
            .where(
                WishMatch.child_id == child.id,
                WishMatch.reward_id == reward.id,
                WishMatch.source == MATCH_MANUAL,
                WishMatch.status == MATCH_ACTIVE,
            )
            .order_by(WishMatch.created_at, WishMatch.id)
        ).all()
    )
    manual_total = sum(match.amount for match in manual_matches)
    auto = calculate_auto_match(
        cost, locked, manual_total, reward.auto_match_percent
    )
    if balance + manual_total + auto < cost:
        raise ValueError("可用积分与家长支持不足，无法通过")

    if reward.stock > 0:
        reward.stock -= 1

    now = utcnow()
    locks = list(
        db.scalars(
            select(SavingsLock)
            .where(
                SavingsLock.child_id == child.id,
                SavingsLock.reward_id == reward.id,
                SavingsLock.status == LOCK_ACTIVE,
            )
            .order_by(SavingsLock.created_at)
        ).all()
    )
    lock_remaining = cost
    lock_used = 0
    for lock in locks:
        if lock_remaining <= 0:
            break
        used = min(lock.amount, lock_remaining)
        lock.amount -= used
        lock_remaining -= used
        lock_used += used
        if lock.amount == 0:
            lock.status = LOCK_REDEEMED
            lock.released_at = now
            lock.released_by_id = reviewer.id
    for lock in locks:
        if lock.status == LOCK_ACTIVE:
            lock.status = LOCK_RELEASED
            lock.released_at = now
            lock.released_by_id = reviewer.id
            lock.note = "兑换后释放多余锁定"

    pool_needed = max(cost - lock_used, 0)
    manual_used = 0
    for match in manual_matches:
        if pool_needed <= 0:
            break
        used = min(match.amount, pool_needed)
        match.used_amount += used
        pool_needed -= used
        manual_used += used
        match.status = MATCH_USED
        match.redemption_id = redemption.id
        if match.used_amount < match.amount:
            match.note = (match.note + "（未使用部分已作废）").strip()
    auto_used = min(auto, pool_needed)
    if auto_used > 0:
        db.add(
            WishMatch(
                family_id=child.family_id,
                child_id=child.id,
                reward_id=reward.id,
                parent_id=reviewer.id,
                amount=auto_used,
                used_amount=auto_used,
                source=MATCH_AUTO,
                status=MATCH_USED,
                note=f"自动配捐 {reward.auto_match_percent}%",
                ratio_snapshot=reward.auto_match_percent,
                redemption_id=redemption.id,
            )
        )

    db.flush()
    remaining_active = db.scalars(
        select(WishMatch).where(
            WishMatch.child_id == child.id,
            WishMatch.reward_id == reward.id,
            WishMatch.status == MATCH_ACTIVE,
        )
    ).all()
    for match in remaining_active:
        match.status = MATCH_VOIDED
        match.voided_at = now

    paid_from_balance = cost - manual_used - auto_used
    _create_transaction(
        db,
        family_id=child.family_id,
        child_id=child.id,
        delta=-paid_from_balance,
        kind="redeem",
        note=f"兑换：{reward.title}",
        ref_type="redemption",
        ref_id=redemption.id,
    )

    redemption.status = REDEMPTION_APPROVED
    redemption.reviewed_by_id = reviewer.id
    redemption.reviewed_at = now
    redemption.review_note = note
    return redemption


def fulfill_redemption(
    db: Session, redemption: Redemption
) -> Redemption:
    if redemption.status != REDEMPTION_APPROVED:
        raise ValueError("只有已通过的兑换才能标记兑现")
    redemption.status = REDEMPTION_FULFILLED
    redemption.fulfilled_at = utcnow()
    return redemption


def lock_savings(
    db: Session,
    child: Member,
    reward: Reward,
    amount: int,
    note: str,
) -> SavingsLock:
    if not reward.active:
        raise ValueError("奖励已下架")
    if not reward.is_long_term:
        raise ValueError("只有长期心愿可以锁定储蓄")
    if amount <= 0:
        raise ValueError("锁定积分必须大于 0")
    if get_available(db, child.id) < amount:
        raise ValueError("可用积分不足")
    lock = SavingsLock(
        family_id=child.family_id,
        child_id=child.id,
        reward_id=reward.id,
        amount=amount,
        status=LOCK_ACTIVE,
        note=note.strip(),
        created_at=utcnow(),
    )
    db.add(lock)
    db.flush()
    return lock


def release_savings(
    db: Session, lock: SavingsLock, reviewer: Member
) -> SavingsLock:
    if lock.status != LOCK_ACTIVE:
        raise ValueError("该锁定已经释放或使用")
    lock.status = LOCK_RELEASED
    lock.released_at = utcnow()
    lock.released_by_id = reviewer.id
    return lock


def create_manual_match(
    db: Session,
    parent: Member,
    child: Member,
    reward: Reward,
    amount: int,
    note: str,
) -> WishMatch:
    if not reward.is_long_term:
        raise ValueError("只有长期心愿可以配捐")
    if not reward.active:
        raise ValueError("心愿已下架")
    if amount <= 0:
        raise ValueError("配捐积分必须大于 0")
    match = WishMatch(
        family_id=parent.family_id,
        child_id=child.id,
        reward_id=reward.id,
        parent_id=parent.id,
        amount=amount,
        used_amount=0,
        source=MATCH_MANUAL,
        status=MATCH_ACTIVE,
        note=note.strip(),
        created_at=utcnow(),
    )
    db.add(match)
    db.flush()
    return match


def revoke_match(db: Session, match: WishMatch) -> WishMatch:
    if match.source != MATCH_MANUAL:
        raise ValueError("自动配捐没有可撤销记录")
    if match.status != MATCH_ACTIVE:
        raise ValueError("该配捐已经使用或作废")
    match.status = MATCH_REVOKED
    match.voided_at = utcnow()
    return match


def void_matches_for_reward(
    db: Session, reward_id: int, child_id: int | None = None
) -> None:
    stmt = select(WishMatch).where(
        WishMatch.reward_id == reward_id,
        WishMatch.status == MATCH_ACTIVE,
    )
    if child_id is not None:
        stmt = stmt.where(WishMatch.child_id == child_id)
    now = utcnow()
    for match in db.scalars(stmt).all():
        match.status = MATCH_VOIDED
        match.voided_at = now


def serialize_wish(db: Session, wish: Wish) -> WishOut:
    child = db.get(Member, wish.child_id)
    reward = db.get(Reward, wish.reward_id) if wish.reward_id else None
    return WishOut(
        id=wish.id,
        child_id=wish.child_id,
        child_name=child.name if child else "",
        title=wish.title,
        emoji=wish.emoji,
        image_url=media_url(wish.image_path),
        reason=wish.reason,
        expected_points=wish.expected_points,
        status=wish.status,
        reward_id=wish.reward_id,
        reward_title=reward.title if reward else None,
        reject_reason=wish.reject_reason,
        created_at=wish.created_at,
        reviewed_at=wish.reviewed_at,
    )


def create_wish(
    db: Session,
    child: Member,
    title: str,
    emoji: str,
    reason: str,
    expected_points: int,
    image_path: str | None,
) -> Wish:
    if not title.strip():
        raise ValueError("心愿需要一个名字")
    wish = Wish(
        family_id=child.family_id,
        child_id=child.id,
        title=title.strip(),
        emoji=emoji or "🌟",
        image_path=image_path,
        reason=reason.strip(),
        expected_points=max(0, expected_points),
        status=WISH_PENDING,
        created_at=utcnow(),
    )
    db.add(wish)
    db.flush()
    return wish


def list_wish_as_reward(
    db: Session,
    wish: Wish,
    reviewer: Member,
    payload,
) -> Reward:
    if wish.status == WISH_LISTED:
        raise ValueError("这个心愿已经上架")
    reward = Reward(
        family_id=wish.family_id,
        title=(payload.title or wish.title).strip(),
        emoji=(payload.emoji or wish.emoji or "🎁"),
        description=payload.description or wish.reason,
        value=payload.value,
        unit=payload.unit,
        multiplier=payload.multiplier,
        cost_points=calculate_cost(payload.value, payload.multiplier),
        stock=payload.stock,
        is_long_term=payload.is_long_term,
        auto_match_percent=payload.auto_match_percent,
        active=True,
    )
    db.add(reward)
    db.flush()
    wish.status = WISH_LISTED
    wish.reward_id = reward.id
    wish.reviewed_by_id = reviewer.id
    wish.reviewed_at = utcnow()
    wish.reject_reason = ""
    return reward


def reject_wish(
    db: Session, wish: Wish, reviewer: Member, reason: str
) -> Wish:
    if wish.status == WISH_LISTED:
        raise ValueError("已上架的心愿不能驳回")
    if not reason.strip():
        raise ValueError("请填写驳回原因")
    wish.status = WISH_REJECTED
    wish.reject_reason = reason.strip()
    wish.reviewed_by_id = reviewer.id
    wish.reviewed_at = utcnow()
    return wish


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def _task_expected_count(
    task: Task, start: date, end: date, settings: Settings
) -> int:
    created = to_local(task.created_at, settings).date()
    effective_start = max(start, created)
    effective_end = min(end, local_today(settings))
    if effective_start > effective_end:
        return 0
    if task.task_type == "once":
        return 1 if start <= created <= end else 0
    if task.task_type == "weekly":
        first_week = effective_start - timedelta(days=effective_start.weekday())
        weeks = set()
        cursor = first_week
        while cursor <= effective_end:
            weeks.add(cursor)
            cursor += timedelta(days=7)
        return len(weeks)
    days = 0
    cursor = effective_start
    while cursor <= effective_end:
        if task_applies_on(task, cursor):
            days += 1
        cursor += timedelta(days=1)
    return days


def build_stats(
    db: Session,
    child: Member,
    period: str,
    anchor: date | None,
    settings: Settings,
) -> StatsOut:
    start, end, label = period_bounds(period, anchor, settings)
    start_utc = local_date_start_utc(start, settings)
    end_utc = local_date_end_utc(end, settings)
    transactions = list(
        db.scalars(
            select(PointTransaction).where(
                PointTransaction.child_id == child.id,
                PointTransaction.created_at >= start_utc,
                PointTransaction.created_at < end_utc,
            )
        ).all()
    )
    task_points = sum(
        row.delta for row in transactions if row.kind == "task"
    )
    bonus_points = sum(
        row.delta for row in transactions if row.kind == "streak_bonus"
    )
    redeemed_points = sum(
        abs(row.delta) for row in transactions if row.kind == "redeem"
    )
    adjusted_points = sum(
        row.delta for row in transactions if row.kind == "adjust"
    )
    net_points = sum(row.delta for row in transactions)

    buckets = []
    for bucket_start, bucket_end, bucket_label in bucket_starts(
        start, end, period
    ):
        low = local_date_start_utc(bucket_start, settings)
        high = local_date_end_utc(bucket_end, settings)
        rows = [
            row
            for row in transactions
            if as_utc(row.created_at) >= low and as_utc(row.created_at) < high
        ]
        buckets.append(
            StatsBucket(
                label=bucket_label,
                task_points=sum(row.delta for row in rows if row.kind == "task"),
                bonus_points=sum(
                    row.delta for row in rows if row.kind == "streak_bonus"
                ),
                redeemed_points=sum(
                    abs(row.delta) for row in rows if row.kind == "redeem"
                ),
                adjusted_points=sum(
                    row.delta for row in rows if row.kind == "adjust"
                ),
                net_points=sum(row.delta for row in rows),
            )
        )

    tasks = db.scalars(
        select(Task).where(Task.child_id == child.id)
    ).all()
    expected = sum(
        _task_expected_count(task, start, end, settings) for task in tasks
    )
    approved = int(
        db.scalar(
            select(func.count(Submission.id)).where(
                Submission.child_id == child.id,
                Submission.status == SUBMISSION_APPROVED,
                Submission.submitted_at >= start_utc,
                Submission.submitted_at < end_utc,
            )
        )
        or 0
    )
    rate = min(100, round(approved * 100 / expected)) if expected else 0

    redemptions = db.scalars(
        select(Redemption).where(
            Redemption.child_id == child.id,
            Redemption.requested_at >= start_utc,
            Redemption.requested_at < end_utc,
        )
    ).all()
    statuses: dict[str, int] = {}
    for redemption in redemptions:
        statuses[redemption.status] = statuses.get(redemption.status, 0) + 1
    redemption_points = sum(
        redemption.cost_points
        for redemption in redemptions
        if redemption.status in (REDEMPTION_APPROVED, REDEMPTION_FULFILLED)
    )
    return StatsOut(
        child_id=child.id,
        child_name=child.name,
        period=period,
        label=label,
        start_date=start,
        end_date=end,
        task_points=task_points,
        bonus_points=bonus_points,
        redeemed_points=redeemed_points,
        adjusted_points=adjusted_points,
        net_points=net_points,
        task_completion=StatsTaskRate(
            approved=approved, expected=expected, percent=rate
        ),
        redemption_count=len(redemptions),
        redemption_points=redemption_points,
        redemption_statuses=statuses,
        buckets=buckets,
        has_data=bool(transactions or approved or redemptions),
    )


# ---------------------------------------------------------------------------
# Today tasks and composite views
# ---------------------------------------------------------------------------


def _submission_status(submission: Submission | None) -> str:
    if submission is None:
        return "todo"
    if submission.status == SUBMISSION_APPROVED:
        return "done"
    if submission.status == SUBMISSION_REJECTED:
        return "rejected"
    return "pending"


def get_today_tasks(
    db: Session, child: Member, settings: Settings
) -> list[TodayTaskOut]:
    tasks = db.scalars(
        select(Task)
        .where(Task.child_id == child.id, Task.active.is_(True))
        .order_by(Task.created_at)
    ).all()
    result: list[TodayTaskOut] = []
    today = local_today(settings)
    for task in tasks:
        if not task_applies_on(task, today):
            continue
        key = period_key(task.task_type, settings)
        submission = db.scalar(
            select(Submission).where(
                Submission.task_id == task.id,
                Submission.period_key == key,
            )
        )
        if (
            task.task_type == "once"
            and submission is not None
            and submission.status == SUBMISSION_APPROVED
        ):
            continue
        base = serialize_task(db, task, settings)
        result.append(
            TodayTaskOut(
                **base.model_dump(),
                child_name=child.name,
                status=_submission_status(submission),
                submission_id=submission.id if submission else None,
            )
        )
    return result


def build_child_home(
    db: Session, child: Member, settings: Settings
) -> ChildHome:
    balance = get_balance(db, child.id)
    locked = get_locked_total(db, child.id)
    lifetime = get_lifetime_earned(db, child.id)
    level, level_progress, next_level_points = level_info(
        db, child.family_id, lifetime
    )
    badges = get_badges(db, child.id)
    goals = db.scalars(
        select(Goal)
        .where(Goal.child_id == child.id, Goal.status != "archived")
        .order_by(Goal.created_at.desc())
    ).all()
    long_term_rewards = db.scalars(
        select(Reward)
        .where(
            Reward.family_id == child.family_id,
            Reward.active.is_(True),
            Reward.is_long_term.is_(True),
        )
        .order_by(Reward.created_at.desc())
    ).all()
    transactions = db.scalars(
        select(PointTransaction)
        .where(PointTransaction.child_id == child.id)
        .order_by(PointTransaction.created_at.desc())
        .limit(10)
    ).all()
    redemptions = db.scalars(
        select(Redemption)
        .where(Redemption.child_id == child.id)
        .order_by(Redemption.requested_at.desc())
        .limit(5)
    ).all()
    return ChildHome(
        member=serialize_member(child),
        family_name=get_family_name(db, child.family_id),
        balance=balance,
        available=balance - locked,
        locked=locked,
        lifetime_earned=lifetime,
        level=level,
        level_progress=level_progress,
        next_level_points=next_level_points,
        streak_days=get_streak_days(db, child.id, settings),
        badges=[serialize_badge(db, badge) for badge in badges],
        today_tasks=get_today_tasks(db, child, settings),
        goals=[serialize_goal(db, goal) for goal in goals],
        long_term_rewards=[
            serialize_reward(
                db, reward, child.id, settings, include_locks=True
            )
            for reward in long_term_rewards
        ],
        recent_transactions=[
            serialize_transaction(transaction) for transaction in transactions
        ],
        recent_redemptions=[
            serialize_redemption(db, redemption) for redemption in redemptions
        ],
    )


def build_parent_dashboard(
    db: Session, parent: Member, settings: Settings
) -> ParentDashboard:
    children = db.scalars(
        select(Member)
        .where(
            Member.family_id == parent.family_id,
            Member.role == ROLE_CHILD,
            Member.is_active.is_(True),
        )
        .order_by(Member.created_at)
    ).all()
    child_ids = [child.id for child in children]
    summaries = [
        ChildSummary(
            member=serialize_member(child),
            balance=get_balance(db, child.id),
            available=get_available(db, child.id),
            locked=get_locked_total(db, child.id),
            week_earned=get_week_earned(db, child.id, settings),
            level=level_info(
                db, child.family_id, get_lifetime_earned(db, child.id)
            )[0],
        )
        for child in children
    ]

    pending_submissions = (
        db.scalars(
            select(Submission)
            .where(
                Submission.child_id.in_(child_ids),
                Submission.status == SUBMISSION_PENDING,
            )
            .order_by(Submission.submitted_at)
        ).all()
        if child_ids
        else []
    )
    pending_redemptions = (
        db.scalars(
            select(Redemption)
            .where(
                Redemption.child_id.in_(child_ids),
                Redemption.status == REDEMPTION_PENDING,
            )
            .order_by(Redemption.requested_at)
        ).all()
        if child_ids
        else []
    )
    unfulfilled = (
        db.scalars(
            select(Redemption)
            .where(
                Redemption.child_id.in_(child_ids),
                Redemption.status == REDEMPTION_APPROVED,
                Redemption.fulfilled_at.is_(None),
            )
            .order_by(Redemption.reviewed_at)
        ).all()
        if child_ids
        else []
    )
    active_locks = (
        db.scalars(
            select(SavingsLock)
            .where(
                SavingsLock.child_id.in_(child_ids),
                SavingsLock.status == LOCK_ACTIVE,
            )
            .order_by(SavingsLock.created_at.desc())
        ).all()
        if child_ids
        else []
    )
    today_tasks: list[TodayTaskOut] = []
    for child in children:
        today_tasks.extend(get_today_tasks(db, child, settings))
    pending_wish_count = int(
        db.scalar(
            select(func.count(Wish.id)).where(
                Wish.family_id == parent.family_id,
                Wish.status == WISH_PENDING,
            )
        )
        or 0
    )

    return ParentDashboard(
        family_name=get_family_name(db, parent.family_id),
        children=summaries,
        pending_submissions=[
            serialize_submission(db, row) for row in pending_submissions
        ],
        pending_redemptions=[
            serialize_redemption(db, row) for row in pending_redemptions
        ],
        unfulfilled_redemptions=[
            serialize_redemption(db, row) for row in unfulfilled
        ],
        pending_wish_count=pending_wish_count,
        active_locks=[serialize_lock(db, row) for row in active_locks],
        today_tasks=today_tasks,
    )


def build_point_summary(
    db: Session, child: Member, settings: Settings, limit: int = 50
) -> PointSummary:
    balance = get_balance(db, child.id)
    locked = get_locked_total(db, child.id)
    lifetime = get_lifetime_earned(db, child.id)
    level, level_progress, next_level_points = level_info(
        db, child.family_id, lifetime
    )
    transactions = db.scalars(
        select(PointTransaction)
        .where(PointTransaction.child_id == child.id)
        .order_by(PointTransaction.created_at.desc())
        .limit(max(1, min(limit, 200)))
    ).all()
    return PointSummary(
        child_id=child.id,
        balance=balance,
        available=balance - locked,
        locked=locked,
        lifetime_earned=lifetime,
        level=level,
        level_progress=level_progress,
        next_level_points=next_level_points,
        streak_days=get_streak_days(db, child.id, settings),
        badges=[
            serialize_badge(db, badge) for badge in get_badges(db, child.id)
        ],
        transactions=[serialize_transaction(row) for row in transactions],
    )


def create_sample_data(
    db: Session, family_id: int, child: Member
) -> None:
    reading = Goal(
        family_id=family_id,
        child_id=child.id,
        title="养成阅读习惯",
        emoji="📚",
        description="每天读一点，积少成多。",
        target_points=300,
        progress_mode=GOAL_PROGRESS_POINTS,
        target_value=300,
        badge_name="阅读小达人",
        badge_emoji="📖",
        status="active",
    )
    db.add(reading)
    db.flush()
    db.add_all(
        [
            GoalStage(
                goal_id=reading.id,
                sort_order=0,
                threshold_value=100,
                badge_name="阅读起步",
                badge_emoji="🌱",
            ),
            GoalStage(
                goal_id=reading.id,
                sort_order=1,
                threshold_value=200,
                badge_name="阅读进阶",
                badge_emoji="🌿",
            ),
        ]
    )

    db.add_all(
        [
            Task(
                family_id=family_id,
                child_id=child.id,
                goal_id=reading.id,
                title="阅读 20 分钟",
                description="任何喜欢的书都可以。",
                points=10,
                task_type="daily",
            ),
            Task(
                family_id=family_id,
                child_id=child.id,
                title="整理书桌",
                description="让学习角清清爽爽。",
                points=5,
                task_type="daily",
            ),
            Task(
                family_id=family_id,
                child_id=child.id,
                goal_id=reading.id,
                title="周末阅读 1 小时",
                description="周末的安静阅读时间。",
                points=15,
                task_type="weekly",
            ),
            Task(
                family_id=family_id,
                child_id=child.id,
                title="完成一次家务挑战",
                description="和爸爸妈妈一起选一件家务。",
                points=30,
                task_type="once",
            ),
        ]
    )
    db.add_all(
        [
            Reward(
                family_id=family_id,
                title="周末游戏时间 60 分钟",
                emoji="🎮",
                description="完成作业后使用。",
                value=60,
                unit="minutes",
                multiplier=1.2,
                cost_points=calculate_cost(60, 1.2),
                stock=-1,
            ),
            Reward(
                family_id=family_id,
                title="现金零花钱 100 元",
                emoji="💵",
                description="线下兑现，自由支配。",
                value=100,
                unit="yuan",
                multiplier=1.5,
                cost_points=calculate_cost(100, 1.5),
                stock=-1,
            ),
            Reward(
                family_id=family_id,
                title="心仪的电脑",
                emoji="💻",
                description="一个值得慢慢积累的大心愿。",
                value=5000,
                unit="points",
                multiplier=1.0,
                cost_points=calculate_cost(5000, 1.0),
                stock=1,
                is_long_term=True,
            ),
            Reward(
                family_id=family_id,
                title="一次家庭电影夜",
                emoji="🎬",
                description="一起选一部电影，准备一点小零食。",
                value=50,
                unit="points",
                multiplier=1.0,
                cost_points=50,
                stock=-1,
            ),
        ]
    )
