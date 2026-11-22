import secrets
from datetime import datetime, timezone
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .auth import (
    clear_session_cookie,
    family_name,
    get_current_member,
    get_db,
    get_settings,
    hash_pin,
    require_child,
    require_parent,
    resolve_child,
    set_session_cookie,
    verify_pin,
)
from .backup import backup_database
from .config import Settings
from .constants import (
    LOCK_ACTIVE,
    REDEMPTION_APPROVED,
    REDEMPTION_FULFILLED,
    REDEMPTION_PENDING,
    REDEMPTION_REJECTED,
    ROLE_CHILD,
    ROLE_PARENT,
    SUBMISSION_APPROVED,
    SUBMISSION_PENDING,
    SUBMISSION_REJECTED,
    TASK_TYPES,
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
    AuthMe,
    BackupOut,
    ChildHome,
    GoalCreate,
    GoalOut,
    GoalUpdate,
    LoginRequest,
    MemberCreate,
    MemberOut,
    MemberPublic,
    MemberUpdate,
    MessageOut,
    ParentDashboard,
    PointAdjustRequest,
    PointSummary,
    RedemptionCreate,
    RedemptionOut,
    ReviewRequest,
    RewardCreate,
    RewardOut,
    RewardUpdate,
    SavingsLockCreate,
    SavingsLockOut,
    SetupRequest,
    SetupStatus,
    SubmissionOut,
    TaskCreate,
    TaskOut,
    TaskUpdate,
    TransactionOut,
)
from .services import (
    adjust_points,
    build_child_home,
    build_parent_dashboard,
    build_point_summary,
    calculate_cost,
    create_redemption,
    create_sample_data,
    fulfill_redemption,
    get_family_name,
    lock_savings,
    release_savings,
    review_redemption,
    review_submission,
    serialize_goal,
    serialize_lock,
    serialize_member,
    serialize_redemption,
    serialize_reward,
    serialize_submission,
    serialize_task,
    serialize_transaction,
    submit_task,
)

router = APIRouter(prefix="/api")

ALLOWED_PHOTO_TYPES = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
MAX_PHOTO_BYTES = 5 * 1024 * 1024


def _bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


def _not_found(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)


def _save_photo(upload: UploadFile, settings: Settings) -> str:
    extension = ALLOWED_PHOTO_TYPES.get((upload.content_type or "").lower())
    if extension is None:
        raise _bad_request("照片仅支持 JPG、PNG 或 WebP")
    content = upload.file.read(MAX_PHOTO_BYTES + 1)
    if len(content) > MAX_PHOTO_BYTES:
        raise _bad_request("照片不能超过 5MB")
    if not content:
        raise _bad_request("照片内容为空")
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{secrets.token_hex(16)}.{extension}"
    (upload_dir / filename).write_bytes(content)
    return f"/uploads/{filename}"


def _remove_photo(photo_path: str | None, settings: Settings) -> None:
    if not photo_path or not photo_path.startswith("/uploads/"):
        return
    target = Path(settings.upload_dir) / Path(photo_path).name
    try:
        target.unlink(missing_ok=True)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Health, setup and auth
# ---------------------------------------------------------------------------


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/setup/status", response_model=SetupStatus)
def setup_status(db: Session = Depends(get_db)) -> SetupStatus:
    family = db.scalar(select(Family).limit(1))
    return SetupStatus(
        needs_setup=family is None,
        family_name=family.name if family else None,
    )


@router.post("/setup", response_model=AuthMe)
def setup(
    payload: SetupRequest,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthMe:
    if db.scalar(select(Family.id).limit(1)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="家庭已经初始化"
        )
    family = Family(name=payload.family_name.strip())
    db.add(family)
    db.flush()

    parent = Member(
        family_id=family.id,
        name=payload.parent.name.strip(),
        role=ROLE_PARENT,
        avatar=payload.parent.avatar or "🦉",
        pin_hash=hash_pin(payload.parent.pin),
        approval_required=False,
    )
    db.add(parent)
    db.flush()

    child = None
    if payload.child is not None:
        child = Member(
            family_id=family.id,
            name=payload.child.name.strip(),
            role=ROLE_CHILD,
            avatar=payload.child.avatar or "🌱",
            pin_hash=hash_pin(payload.child.pin),
            approval_required=payload.child.approval_required,
        )
        db.add(child)
        db.flush()

    if payload.create_samples and child is not None:
        create_sample_data(db, family.id, child)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    set_session_cookie(response, settings, parent)
    return AuthMe(
        member=serialize_member(parent), family_name=family.name
    )


@router.get("/auth/members", response_model=list[MemberPublic])
def auth_members(db: Session = Depends(get_db)) -> list[MemberPublic]:
    members = db.scalars(
        select(Member)
        .where(Member.is_active.is_(True))
        .order_by(Member.role.desc(), Member.id)
    ).all()
    return [
        MemberPublic(
            id=member.id,
            name=member.name,
            avatar=member.avatar,
            role=member.role,
        )
        for member in members
    ]


@router.post("/auth/login", response_model=AuthMe)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthMe:
    member = db.get(Member, payload.member_id)
    if (
        member is None
        or not member.is_active
        or not verify_pin(payload.pin, member.pin_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="成员或 PIN 不正确",
        )
    set_session_cookie(response, settings, member)
    return AuthMe(
        member=serialize_member(member),
        family_name=get_family_name(db, member.family_id),
    )


@router.post("/auth/logout", response_model=MessageOut)
def logout(
    response: Response, settings: Settings = Depends(get_settings)
) -> MessageOut:
    clear_session_cookie(response, settings)
    return MessageOut(message="已退出登录")


@router.get("/auth/me", response_model=AuthMe)
def me(
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> AuthMe:
    return AuthMe(
        member=serialize_member(current),
        family_name=get_family_name(db, current.family_id),
    )


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


@router.get("/members", response_model=list[MemberOut])
def list_members(
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
) -> list[MemberOut]:
    members = db.scalars(
        select(Member)
        .where(Member.family_id == current.family_id)
        .order_by(Member.role.desc(), Member.created_at)
    ).all()
    return [serialize_member(member) for member in members]


@router.post("/members", response_model=MemberOut)
def create_member(
    payload: MemberCreate,
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
) -> MemberOut:
    member = Member(
        family_id=current.family_id,
        name=payload.name.strip(),
        role=payload.role,
        avatar=payload.avatar or ("🦉" if payload.role == ROLE_PARENT else "🌱"),
        pin_hash=hash_pin(payload.pin),
        approval_required=(
            payload.approval_required if payload.role == ROLE_CHILD else False
        ),
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return serialize_member(member)


@router.patch("/members/{member_id}", response_model=MemberOut)
def update_member(
    member_id: int,
    payload: MemberUpdate,
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
) -> MemberOut:
    member = db.get(Member, member_id)
    if member is None or member.family_id != current.family_id:
        raise _not_found("成员不存在")
    data = payload.model_dump(exclude_unset=True)
    if data.get("is_active") is False and member.id == current.id:
        raise _bad_request("不能停用当前登录的家长")
    if data.get("is_active") is False and member.role == ROLE_PARENT:
        other_parents = int(
            db.scalar(
                select(func.count(Member.id)).where(
                    Member.family_id == current.family_id,
                    Member.role == ROLE_PARENT,
                    Member.is_active.is_(True),
                    Member.id != member.id,
                )
            )
            or 0
        )
        if other_parents == 0:
            raise _bad_request("至少需要保留一位启用的家长")
    if member.role == ROLE_PARENT:
        data.pop("approval_required", None)
    pin = data.pop("pin", None)
    for key, value in data.items():
        setattr(member, key, value)
    if pin is not None:
        member.pin_hash = hash_pin(pin)
    db.commit()
    db.refresh(member)
    return serialize_member(member)


# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------


@router.get("/goals", response_model=list[GoalOut])
def list_goals(
    child_id: int | None = Query(default=None),
    include_archived: bool = Query(default=False),
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> list[GoalOut]:
    stmt = select(Goal)
    if current.role == ROLE_CHILD:
        stmt = stmt.where(Goal.child_id == current.id)
        if not include_archived:
            stmt = stmt.where(Goal.status != "archived")
    else:
        stmt = stmt.where(Goal.family_id == current.family_id)
        if child_id is not None:
            child = resolve_child(db, current, child_id)
            stmt = stmt.where(Goal.child_id == child.id)
        if not include_archived:
            stmt = stmt.where(Goal.status != "archived")
    goals = db.scalars(stmt.order_by(Goal.created_at.desc())).all()
    return [serialize_goal(db, goal) for goal in goals]


@router.post("/goals", response_model=GoalOut)
def create_goal(
    payload: GoalCreate,
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
) -> GoalOut:
    child = resolve_child(db, current, payload.child_id)
    if (
        payload.start_date is not None
        and payload.end_date is not None
        and payload.start_date > payload.end_date
    ):
        raise _bad_request("开始日期不能晚于结束日期")
    goal = Goal(
        family_id=current.family_id,
        child_id=child.id,
        title=payload.title.strip(),
        emoji=payload.emoji or "🎯",
        description=payload.description,
        target_points=payload.target_points,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return serialize_goal(db, goal)


@router.patch("/goals/{goal_id}", response_model=GoalOut)
def update_goal(
    goal_id: int,
    payload: GoalUpdate,
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
) -> GoalOut:
    goal = db.get(Goal, goal_id)
    if goal is None or goal.family_id != current.family_id:
        raise _not_found("目标不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(goal, key, value)
    if (
        goal.start_date is not None
        and goal.end_date is not None
        and goal.start_date > goal.end_date
    ):
        raise _bad_request("开始日期不能晚于结束日期")
    db.commit()
    db.refresh(goal)
    return serialize_goal(db, goal)


@router.delete("/goals/{goal_id}", response_model=MessageOut)
def delete_goal(
    goal_id: int,
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
) -> MessageOut:
    goal = db.get(Goal, goal_id)
    if goal is None or goal.family_id != current.family_id:
        raise _not_found("目标不存在")
    db.execute(update(Task).where(Task.goal_id == goal.id).values(goal_id=None))
    db.delete(goal)
    db.commit()
    return MessageOut(message="目标已删除")


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(
    child_id: int | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> list[TaskOut]:
    stmt = select(Task)
    if current.role == ROLE_CHILD:
        stmt = stmt.where(Task.child_id == current.id, Task.active.is_(True))
    else:
        stmt = stmt.where(Task.family_id == current.family_id)
        if child_id is not None:
            child = resolve_child(db, current, child_id)
            stmt = stmt.where(Task.child_id == child.id)
        if not include_inactive:
            stmt = stmt.where(Task.active.is_(True))
    tasks = db.scalars(stmt.order_by(Task.created_at)).all()
    return [serialize_task(db, task) for task in tasks]


@router.post("/tasks", response_model=TaskOut)
def create_task(
    payload: TaskCreate,
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
) -> TaskOut:
    child = resolve_child(db, current, payload.child_id)
    if payload.goal_id is not None:
        goal = db.get(Goal, payload.goal_id)
        if (
            goal is None
            or goal.family_id != current.family_id
            or goal.child_id != child.id
        ):
            raise _bad_request("目标不属于这个孩子")
    if payload.task_type not in TASK_TYPES:
        raise _bad_request("任务周期不正确")
    task = Task(
        family_id=current.family_id,
        child_id=child.id,
        goal_id=payload.goal_id,
        title=payload.title.strip(),
        description=payload.description,
        points=payload.points,
        task_type=payload.task_type,
        requires_photo=payload.requires_photo,
        active=payload.active,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return serialize_task(db, task)


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
) -> TaskOut:
    task = db.get(Task, task_id)
    if task is None or task.family_id != current.family_id:
        raise _not_found("任务不存在")
    data = payload.model_dump(exclude_unset=True)
    if "goal_id" in data and data["goal_id"] is not None:
        goal = db.get(Goal, data["goal_id"])
        if (
            goal is None
            or goal.family_id != current.family_id
            or goal.child_id != task.child_id
        ):
            raise _bad_request("目标不属于这个孩子")
    for key, value in data.items():
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return serialize_task(db, task)


# ---------------------------------------------------------------------------
# Submissions and review
# ---------------------------------------------------------------------------


@router.post("/submissions", response_model=SubmissionOut)
def create_submission(
    task_id: int = Form(...),
    note: str = Form(default=""),
    photo: UploadFile | None = File(default=None),
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SubmissionOut:
    task = db.get(Task, task_id)
    if task is None or task.family_id != current.family_id:
        raise _not_found("任务不存在")
    if current.role == ROLE_CHILD and task.child_id != current.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="不能提交其他孩子的任务"
        )
    child = db.get(Member, task.child_id)
    if (
        child is None
        or child.family_id != current.family_id
        or not child.is_active
    ):
        raise _not_found("任务所属孩子不存在")
    if len(note) > 500:
        raise _bad_request("备注不能超过 500 字")
    photo_path = _save_photo(photo, settings) if photo is not None else None
    try:
        submission = submit_task(
            db, task, current, note, photo_path, settings
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        _remove_photo(photo_path, settings)
        raise _bad_request(str(exc))
    db.refresh(submission)
    return serialize_submission(db, submission)


@router.get("/submissions", response_model=list[SubmissionOut])
def list_submissions(
    child_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> list[SubmissionOut]:
    if current.role == ROLE_CHILD:
        ids = [current.id]
    elif child_id is not None:
        ids = [resolve_child(db, current, child_id).id]
    else:
        ids = list(
            db.scalars(
                select(Member.id).where(
                    Member.family_id == current.family_id,
                    Member.role == ROLE_CHILD,
                )
            ).all()
        )
    if not ids:
        return []
    stmt = select(Submission).where(Submission.child_id.in_(ids))
    if status_filter:
        stmt = stmt.where(Submission.status == status_filter)
    rows = db.scalars(
        stmt.order_by(Submission.submitted_at.desc()).limit(limit)
    ).all()
    return [serialize_submission(db, row) for row in rows]


@router.get("/submissions/pending", response_model=list[SubmissionOut])
def pending_submissions(
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
) -> list[SubmissionOut]:
    rows = db.scalars(
        select(Submission)
        .where(
            Submission.child_id.in_(
                select(Member.id).where(
                    Member.family_id == current.family_id,
                    Member.role == ROLE_CHILD,
                )
            ),
            Submission.status == SUBMISSION_PENDING,
        )
        .order_by(Submission.submitted_at)
    ).all()
    return [serialize_submission(db, row) for row in rows]


@router.post("/submissions/{submission_id}/review", response_model=SubmissionOut)
def review_submission_endpoint(
    submission_id: int,
    payload: ReviewRequest,
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
) -> SubmissionOut:
    submission = db.get(Submission, submission_id)
    if submission is None or submission.child_id not in [
        member.id
        for member in db.scalars(
            select(Member).where(
                Member.family_id == current.family_id,
                Member.role == ROLE_CHILD,
            )
        ).all()
    ]:
        raise _not_found("提交记录不存在")
    try:
        review_submission(
            db, submission, current, payload.approve, payload.note
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise _bad_request(str(exc))
    db.refresh(submission)
    return serialize_submission(db, submission)


# ---------------------------------------------------------------------------
# Points
# ---------------------------------------------------------------------------


@router.get("/points", response_model=PointSummary)
def points(
    child_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PointSummary:
    if current.role == ROLE_CHILD:
        child = current
    else:
        if child_id is None:
            raise _bad_request("请选择孩子")
        child = resolve_child(db, current, child_id)
    return build_point_summary(db, child, settings, limit)


@router.post("/points/adjust", response_model=TransactionOut)
def adjust_points_endpoint(
    payload: PointAdjustRequest,
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
) -> TransactionOut:
    child = resolve_child(db, current, payload.child_id)
    try:
        transaction = adjust_points(db, child, payload.delta, payload.note)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise _bad_request(str(exc))
    db.refresh(transaction)
    return serialize_transaction(transaction)


# ---------------------------------------------------------------------------
# Rewards
# ---------------------------------------------------------------------------


@router.get("/rewards", response_model=list[RewardOut])
def list_rewards(
    child_id: int | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[RewardOut]:
    if current.role == ROLE_CHILD:
        progress_child_id = current.id
        stmt = select(Reward).where(
            Reward.family_id == current.family_id,
            Reward.active.is_(True),
        )
    else:
        progress_child_id = (
            resolve_child(db, current, child_id).id if child_id else None
        )
        stmt = select(Reward).where(Reward.family_id == current.family_id)
        if not include_inactive:
            stmt = stmt.where(Reward.active.is_(True))
    rewards = db.scalars(
        stmt.order_by(Reward.active.desc(), Reward.created_at.desc())
    ).all()
    return [
        serialize_reward(db, reward, progress_child_id, settings)
        for reward in rewards
    ]


@router.get("/rewards/{reward_id}", response_model=RewardOut)
def get_reward(
    reward_id: int,
    child_id: int | None = Query(default=None),
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RewardOut:
    reward = db.get(Reward, reward_id)
    if reward is None or reward.family_id != current.family_id:
        raise _not_found("奖励不存在")
    if current.role == ROLE_CHILD:
        progress_child_id = current.id
    else:
        progress_child_id = (
            resolve_child(db, current, child_id).id if child_id else None
        )
    return serialize_reward(
        db, reward, progress_child_id, settings, include_locks=True
    )


@router.post("/rewards", response_model=RewardOut)
def create_reward(
    payload: RewardCreate,
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RewardOut:
    reward = Reward(
        family_id=current.family_id,
        title=payload.title.strip(),
        emoji=payload.emoji or "🎁",
        description=payload.description,
        value=payload.value,
        unit=payload.unit,
        multiplier=payload.multiplier,
        cost_points=calculate_cost(payload.value, payload.multiplier),
        stock=payload.stock,
        is_long_term=payload.is_long_term,
        active=payload.active,
    )
    db.add(reward)
    db.commit()
    db.refresh(reward)
    return serialize_reward(db, reward, None, settings)


@router.patch("/rewards/{reward_id}", response_model=RewardOut)
def update_reward(
    reward_id: int,
    payload: RewardUpdate,
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RewardOut:
    reward = db.get(Reward, reward_id)
    if reward is None or reward.family_id != current.family_id:
        raise _not_found("奖励不存在")
    data = payload.model_dump(exclude_unset=True)
    active_locks = int(
        db.scalar(
            select(func.count(SavingsLock.id)).where(
                SavingsLock.reward_id == reward.id,
                SavingsLock.status == LOCK_ACTIVE,
            )
        )
        or 0
    )
    if reward.is_long_term and active_locks:
        if data.get("is_long_term") is False or data.get("active") is False:
            raise _bad_request("请先释放该心愿的锁定积分")
    for key, value in data.items():
        setattr(reward, key, value)
    if "value" in data or "multiplier" in data:
        reward.cost_points = calculate_cost(reward.value, reward.multiplier)
    db.commit()
    db.refresh(reward)
    return serialize_reward(db, reward, None, settings, include_locks=True)


@router.delete("/rewards/{reward_id}", response_model=MessageOut)
def deactivate_reward(
    reward_id: int,
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
) -> MessageOut:
    reward = db.get(Reward, reward_id)
    if reward is None or reward.family_id != current.family_id:
        raise _not_found("奖励不存在")
    active_locks = int(
        db.scalar(
            select(func.count(SavingsLock.id)).where(
                SavingsLock.reward_id == reward.id,
                SavingsLock.status == LOCK_ACTIVE,
            )
        )
        or 0
    )
    if reward.is_long_term and active_locks:
        raise _bad_request("请先释放该心愿的锁定积分")
    reward.active = False
    db.commit()
    return MessageOut(message="奖励已下架")


# ---------------------------------------------------------------------------
# Redemptions
# ---------------------------------------------------------------------------


@router.post("/redemptions", response_model=RedemptionOut)
def request_redemption(
    payload: RedemptionCreate,
    current: Member = Depends(require_child),
    db: Session = Depends(get_db),
) -> RedemptionOut:
    reward = db.get(Reward, payload.reward_id)
    if reward is None or reward.family_id != current.family_id:
        raise _not_found("奖励不存在")
    try:
        redemption = create_redemption(db, current, reward)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise _bad_request(str(exc))
    db.refresh(redemption)
    return serialize_redemption(db, redemption)


@router.get("/redemptions", response_model=list[RedemptionOut])
def list_redemptions(
    child_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> list[RedemptionOut]:
    if current.role == ROLE_CHILD:
        ids = [current.id]
    elif child_id is not None:
        ids = [resolve_child(db, current, child_id).id]
    else:
        ids = list(
            db.scalars(
                select(Member.id).where(
                    Member.family_id == current.family_id,
                    Member.role == ROLE_CHILD,
                )
            ).all()
        )
    if not ids:
        return []
    stmt = select(Redemption).where(Redemption.child_id.in_(ids))
    if status_filter:
        stmt = stmt.where(Redemption.status == status_filter)
    rows = db.scalars(
        stmt.order_by(Redemption.requested_at.desc()).limit(limit)
    ).all()
    return [serialize_redemption(db, row) for row in rows]


@router.post("/redemptions/{redemption_id}/review", response_model=RedemptionOut)
def review_redemption_endpoint(
    redemption_id: int,
    payload: ReviewRequest,
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
) -> RedemptionOut:
    redemption = db.get(Redemption, redemption_id)
    if redemption is None or redemption.child_id not in [
        member.id
        for member in db.scalars(
            select(Member).where(
                Member.family_id == current.family_id,
                Member.role == ROLE_CHILD,
            )
        ).all()
    ]:
        raise _not_found("兑换申请不存在")
    try:
        review_redemption(
            db, redemption, current, payload.approve, payload.note
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise _bad_request(str(exc))
    db.refresh(redemption)
    return serialize_redemption(db, redemption)


@router.post(
    "/redemptions/{redemption_id}/fulfill", response_model=RedemptionOut
)
def fulfill_redemption_endpoint(
    redemption_id: int,
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
) -> RedemptionOut:
    redemption = db.get(Redemption, redemption_id)
    if redemption is None or redemption.child_id not in [
        member.id
        for member in db.scalars(
            select(Member).where(
                Member.family_id == current.family_id,
                Member.role == ROLE_CHILD,
            )
        ).all()
    ]:
        raise _not_found("兑换申请不存在")
    try:
        fulfill_redemption(db, redemption)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise _bad_request(str(exc))
    db.refresh(redemption)
    return serialize_redemption(db, redemption)


# ---------------------------------------------------------------------------
# Savings locks
# ---------------------------------------------------------------------------


@router.get("/savings", response_model=list[SavingsLockOut])
def list_savings(
    child_id: int | None = Query(default=None),
    include_released: bool = Query(default=False),
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> list[SavingsLockOut]:
    if current.role == ROLE_CHILD:
        ids = [current.id]
    elif child_id is not None:
        ids = [resolve_child(db, current, child_id).id]
    else:
        ids = list(
            db.scalars(
                select(Member.id).where(
                    Member.family_id == current.family_id,
                    Member.role == ROLE_CHILD,
                )
            ).all()
        )
    if not ids:
        return []
    stmt = select(SavingsLock).where(SavingsLock.child_id.in_(ids))
    if not include_released:
        stmt = stmt.where(SavingsLock.status == LOCK_ACTIVE)
    rows = db.scalars(stmt.order_by(SavingsLock.created_at.desc())).all()
    return [serialize_lock(db, row) for row in rows]


@router.post("/savings/lock", response_model=SavingsLockOut)
def lock_savings_endpoint(
    payload: SavingsLockCreate,
    current: Member = Depends(require_child),
    db: Session = Depends(get_db),
) -> SavingsLockOut:
    reward = db.get(Reward, payload.reward_id)
    if reward is None or reward.family_id != current.family_id:
        raise _not_found("奖励不存在")
    try:
        lock = lock_savings(
            db, current, reward, payload.amount, payload.note
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise _bad_request(str(exc))
    db.refresh(lock)
    return serialize_lock(db, lock)


@router.post("/savings/{lock_id}/release", response_model=SavingsLockOut)
def release_savings_endpoint(
    lock_id: int,
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
) -> SavingsLockOut:
    lock = db.get(SavingsLock, lock_id)
    if lock is None or lock.family_id != current.family_id:
        raise _not_found("锁定记录不存在")
    try:
        release_savings(db, lock, current)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise _bad_request(str(exc))
    db.refresh(lock)
    return serialize_lock(db, lock)


# ---------------------------------------------------------------------------
# Composite views and backup
# ---------------------------------------------------------------------------


@router.get("/child/home", response_model=ChildHome)
def child_home(
    current: Member = Depends(require_child),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ChildHome:
    return build_child_home(db, current, settings)


@router.get("/parent/dashboard", response_model=ParentDashboard)
def parent_dashboard(
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ParentDashboard:
    return build_parent_dashboard(db, current, settings)


@router.post("/backup", response_model=BackupOut)
def create_backup(
    current: Member = Depends(require_parent),
    settings: Settings = Depends(get_settings),
) -> BackupOut:
    path = backup_database(settings)
    if path is None:
        raise _bad_request("数据库文件不存在，无法备份")
    return BackupOut(
        filename=path.name,
        created_at=datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.utc
        ),
    )
