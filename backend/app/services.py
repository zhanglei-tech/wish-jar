import math
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import Settings
from .constants import (
    LOCK_ACTIVE,
    LOCK_REDEEMED,
    LOCK_RELEASED,
    REDEMPTION_APPROVED,
    REDEMPTION_FULFILLED,
    REDEMPTION_PENDING,
    REDEMPTION_REJECTED,
    ROLE_CHILD,
    ROLE_PARENT,
    SUBMISSION_APPROVED,
    SUBMISSION_PENDING,
    SUBMISSION_REJECTED,
)
from .models import (
    Family,
    Goal,
    Member,
    PointTransaction,
    Redemption,
    Reward,
    SavingsLock,
    Submission,
    Task,
)
from .schemas import (
    ChildHome,
    ChildSummary,
    GoalOut,
    MemberOut,
    ParentDashboard,
    PointSummary,
    RedemptionOut,
    RewardOut,
    SavingsLockOut,
    SubmissionOut,
    TaskOut,
    TodayTaskOut,
    TransactionOut,
)
from .timeutils import (
    as_utc,
    local_today,
    period_key,
    to_local,
    utcnow,
    week_start_utc,
)


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


def serialize_goal(db: Session, goal: Goal) -> GoalOut:
    earned = int(
        db.scalar(
            select(func.coalesce(func.sum(Submission.points_awarded), 0))
            .select_from(Submission)
            .join(Task, Task.id == Submission.task_id)
            .where(
                Task.goal_id == goal.id,
                Submission.status == SUBMISSION_APPROVED,
            )
        )
        or 0
    )
    task_count = int(
        db.scalar(select(func.count(Task.id)).where(Task.goal_id == goal.id)) or 0
    )
    progress = (
        min(100, round(earned * 100 / goal.target_points))
        if goal.target_points > 0
        else 0
    )
    return GoalOut(
        id=goal.id,
        child_id=goal.child_id,
        title=goal.title,
        emoji=goal.emoji,
        description=goal.description,
        target_points=goal.target_points,
        start_date=goal.start_date,
        end_date=goal.end_date,
        status=goal.status,
        earned_points=earned,
        progress_percent=progress,
        task_count=task_count,
    )


def serialize_task(db: Session, task: Task) -> TaskOut:
    goal = db.get(Goal, task.goal_id) if task.goal_id else None
    return TaskOut(
        id=task.id,
        child_id=task.child_id,
        goal_id=task.goal_id,
        goal_title=goal.title if goal else None,
        title=task.title,
        description=task.description,
        points=task.points,
        task_type=task.task_type,
        requires_photo=task.requires_photo,
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
                PointTransaction.kind == "task",
                PointTransaction.delta > 0,
            )
        )
        or 0
    )


def get_level(lifetime_earned: int) -> int:
    return lifetime_earned // 100 + 1


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
            PointTransaction.kind == "task",
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
                PointTransaction.kind == "task",
                PointTransaction.delta > 0,
                PointTransaction.created_at >= start,
            )
        )
        or 0
    )


def serialize_reward(
    db: Session,
    reward: Reward,
    child_id: int | None,
    settings: Settings,
    include_locks: bool = False,
) -> RewardOut:
    locked = get_locked_total(db, child_id, reward.id) if child_id else 0
    cost = reward.cost_points
    progress = (
        min(100, round(locked * 100 / cost))
        if cost > 0
        else (100 if locked > 0 else 0)
    )
    remaining = max(cost - locked, 0)
    estimated = (
        estimate_days(db, child_id, remaining, reward.is_long_term, settings)
        if child_id
        else None
    )
    locks: list[SavingsLockOut] = []
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
        active=reward.active,
        locked_points=locked,
        progress_percent=progress,
        remaining_points=remaining,
        estimated_days=estimated,
        locks=locks,
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
    note: str = "",
) -> None:
    submission.status = SUBMISSION_APPROVED
    submission.reviewed_by_id = reviewer.id
    submission.reviewed_at = utcnow()
    submission.review_note = note
    submission.points_awarded = task.points
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
        _approve_submission(db, submission, task, submitter)
    return submission


def review_submission(
    db: Session,
    submission: Submission,
    reviewer: Member,
    approve: bool,
    note: str,
) -> Submission:
    if submission.status != SUBMISSION_PENDING:
        raise ValueError("该提交已经审核过")
    task = db.get(Task, submission.task_id)
    if task is None:
        raise ValueError("任务不存在")
    if approve:
        _approve_submission(db, submission, task, reviewer, note)
    else:
        submission.status = SUBMISSION_REJECTED
        submission.reviewed_by_id = reviewer.id
        submission.reviewed_at = utcnow()
        submission.review_note = note
        submission.points_awarded = 0
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
    if available + locked < cost:
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
    available = get_available(db, child.id)
    locked = get_locked_total(db, child.id, reward.id)
    if available + locked < cost:
        raise ValueError("可用积分不足，无法通过")

    if reward.stock > 0:
        reward.stock -= 1

    now = utcnow()
    _create_transaction(
        db,
        family_id=child.family_id,
        child_id=child.id,
        delta=-cost,
        kind="redeem",
        note=f"兑换：{reward.title}",
        ref_type="redemption",
        ref_id=redemption.id,
    )

    locks = db.scalars(
        select(SavingsLock)
        .where(
            SavingsLock.child_id == child.id,
            SavingsLock.reward_id == reward.id,
            SavingsLock.status == LOCK_ACTIVE,
        )
        .order_by(SavingsLock.created_at)
    ).all()
    remaining = cost
    for lock in locks:
        if remaining <= 0:
            break
        used = min(lock.amount, remaining)
        lock.amount -= used
        remaining -= used
        if lock.amount == 0:
            lock.status = LOCK_REDEEMED
            lock.released_at = now
            lock.released_by_id = reviewer.id
    if remaining <= 0:
        for lock in locks:
            if lock.status == LOCK_ACTIVE:
                lock.status = LOCK_RELEASED
                lock.released_at = now
                lock.released_by_id = reviewer.id
                lock.note = "兑换后释放多余锁定"

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
    for task in tasks:
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
        base = serialize_task(db, task)
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
        level=get_level(lifetime),
        level_progress=lifetime % 100,
        streak_days=get_streak_days(db, child.id, settings),
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
            level=get_level(get_lifetime_earned(db, child.id)),
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
        active_locks=[serialize_lock(db, row) for row in active_locks],
        today_tasks=today_tasks,
    )


def build_point_summary(
    db: Session, child: Member, settings: Settings, limit: int = 50
) -> PointSummary:
    balance = get_balance(db, child.id)
    locked = get_locked_total(db, child.id)
    lifetime = get_lifetime_earned(db, child.id)
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
        level=get_level(lifetime),
        level_progress=lifetime % 100,
        streak_days=get_streak_days(db, child.id, settings),
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
        status="active",
    )
    db.add(reading)
    db.flush()

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
