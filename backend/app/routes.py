import csv
import io
import secrets
from datetime import date, datetime, timezone
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
from fastapi.responses import FileResponse
from sqlalchemy import delete, func, or_, select, update
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
    GOAL_ACTIVE,
    GOAL_COMPLETED,
    GOAL_PROGRESS_MODES,
    LOCK_ACTIVE,
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
    TASK_TYPES,
    WISH_PENDING,
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
    AuthMe,
    BackupOut,
    ChildHome,
    GoalCreate,
    GoalOut,
    GoalStageIn,
    GoalStageOut,
    GoalUpdate,
    LevelConfigOut,
    LevelConfigUpdate,
    LevelThresholdOut,
    LoginRequest,
    MatchCreate,
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
    StatsOut,
    SubmissionOut,
    TaskCreate,
    TaskOut,
    TaskUpdate,
    TransactionOut,
    WishListRequest,
    WishMatchOut,
    WishOut,
    WishRejectRequest,
)
from .services import (
    adjust_points,
    build_child_home,
    build_parent_dashboard,
    build_point_summary,
    build_stats,
    calculate_cost,
    create_manual_match,
    create_redemption,
    create_sample_data,
    create_wish,
    fulfill_redemption,
    get_badges,
    get_family_name,
    get_level_thresholds,
    level_info,
    list_wish_as_reward,
    lock_savings,
    media_url,
    release_savings,
    reject_wish,
    review_redemption,
    review_submission,
    revoke_match,
    serialize_badge,
    serialize_goal,
    serialize_lock,
    serialize_match,
    serialize_member,
    serialize_redemption,
    serialize_reward,
    serialize_submission,
    serialize_task,
    serialize_transaction,
    serialize_wish,
    submit_task,
    sync_goal_awards,
    sync_level_badges,
    void_matches_for_reward,
    weekdays_to_string,
)

router = APIRouter(prefix="/api")

ALLOWED_PHOTO_TYPES = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
MAX_PHOTO_BYTES = 5 * 1024 * 1024
MAX_ICON_BYTES = 2 * 1024 * 1024
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


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


def _save_icon(upload: UploadFile, settings: Settings, prefix: str) -> str:
    extension = ALLOWED_PHOTO_TYPES.get((upload.content_type or "").lower())
    if extension is None:
        raise _bad_request("图标仅支持 JPG、PNG 或 WebP")
    content = upload.file.read(MAX_ICON_BYTES + 1)
    if len(content) > MAX_ICON_BYTES:
        raise _bad_request("图标不能超过 2MB")
    if not content:
        raise _bad_request("图标内容为空")
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{prefix}-{secrets.token_hex(12)}.{extension}"
    (upload_dir / filename).write_bytes(content)
    return f"/uploads/{filename}"


def _valid_icon_path(path: str | None, settings: Settings) -> str | None:
    if not path:
        return None
    name = Path(path).name
    if not name or Path(name).suffix.lower() not in IMAGE_SUFFIXES:
        raise _bad_request("图标路径不正确")
    if not (Path(settings.upload_dir) / name).is_file():
        raise _bad_request("图标文件不存在")
    return f"/uploads/{name}"


def _validate_stages(
    stages: list[GoalStageIn], target: int, progress_mode: str
) -> None:
    if len(stages) > 10:
        raise _bad_request("最多只能设置 10 个阶段")
    if stages and target <= 0:
        raise _bad_request("设置阶段前需要填写目标值")
    thresholds = [stage.threshold_value for stage in stages]
    if any(value <= 0 for value in thresholds):
        raise _bad_request("阶段阈值必须大于 0")
    if thresholds != sorted(thresholds) or len(set(thresholds)) != len(thresholds):
        raise _bad_request("阶段阈值必须严格递增")
    if target > 0 and any(value >= target for value in thresholds):
        raise _bad_request("阶段阈值必须小于目标值")
    if progress_mode not in GOAL_PROGRESS_MODES:
        raise _bad_request("进度口径不正确")


def _apply_stages(
    db: Session,
    goal: Goal,
    stages: list[GoalStageIn],
    settings: Settings,
) -> None:
    existing = {
        stage.id: stage
        for stage in db.scalars(
            select(GoalStage).where(GoalStage.goal_id == goal.id)
        ).all()
    }
    keep_ids: set[int] = set()
    for index, item in enumerate(stages):
        badge_image = _valid_icon_path(item.badge_image_path, settings)
        if item.id is not None and item.id in existing:
            stage = existing[item.id]
            keep_ids.add(stage.id)
        else:
            stage = GoalStage(goal_id=goal.id, threshold_value=item.threshold_value)
            db.add(stage)
        stage.sort_order = index
        stage.threshold_value = item.threshold_value
        stage.badge_name = item.badge_name.strip()
        stage.badge_emoji = item.badge_emoji.strip()
        stage.badge_image_path = badge_image
    for stage_id, stage in existing.items():
        if stage_id not in keep_ids:
            db.delete(stage)
    db.flush()


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
# Icons and controlled media
# ---------------------------------------------------------------------------


@router.post("/icons")
def upload_icon(
    file: UploadFile = File(...),
    current: Member = Depends(require_parent),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    path = _save_icon(file, settings, "icon")
    return {"path": path, "url": media_url(path) or ""}


@router.get("/media/{filename}")
def get_media(
    filename: str,
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    if (
        not filename
        or Path(filename).name != filename
        or Path(filename).suffix.lower() not in IMAGE_SUFFIXES
    ):
        raise _not_found("图片不存在")
    target = Path(settings.upload_dir) / filename
    if not target.is_file():
        raise _not_found("图片不存在")
    path = f"/uploads/{filename}"
    in_goals = db.scalar(
        select(Goal.id).where(
            Goal.family_id == current.family_id,
            or_(
                Goal.icon_image_path == path,
                Goal.badge_image_path == path,
            ),
        )
    )
    in_stages = db.scalar(
        select(GoalStage.id)
        .join(Goal, Goal.id == GoalStage.goal_id)
        .where(
            Goal.family_id == current.family_id,
            GoalStage.badge_image_path == path,
        )
    )
    in_badges = db.scalar(
        select(ChildBadge.id).where(
            ChildBadge.family_id == current.family_id,
            ChildBadge.image_path == path,
        )
    )
    in_wishes = db.scalar(
        select(Wish.id).where(
            Wish.family_id == current.family_id,
            Wish.image_path == path,
        )
    )
    if not any((in_goals, in_stages, in_badges, in_wishes)):
        raise _not_found("图片不存在")
    return FileResponse(target)


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
    settings: Settings = Depends(get_settings),
) -> GoalOut:
    child = resolve_child(db, current, payload.child_id)
    if (
        payload.start_date is not None
        and payload.end_date is not None
        and payload.start_date > payload.end_date
    ):
        raise _bad_request("开始日期不能晚于结束日期")
    target = (
        payload.target_value
        if payload.target_value is not None
        else (payload.target_points or 0)
    )
    try:
        _validate_stages(payload.stages, target, payload.progress_mode)
        icon_path = _valid_icon_path(payload.icon_image_path, settings)
        badge_image = _valid_icon_path(payload.badge_image_path, settings)
    except HTTPException:
        raise
    goal = Goal(
        family_id=current.family_id,
        child_id=child.id,
        title=payload.title.strip(),
        emoji=payload.emoji or "🎯",
        icon_image_path=icon_path,
        description=payload.description,
        progress_mode=payload.progress_mode,
        target_value=target,
        target_points=target if payload.progress_mode == "points" else 0,
        badge_name=payload.badge_name.strip(),
        badge_emoji=payload.badge_emoji.strip(),
        badge_image_path=badge_image,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    db.add(goal)
    db.flush()
    _apply_stages(db, goal, payload.stages, settings)
    db.commit()
    db.refresh(goal)
    return serialize_goal(db, goal)


@router.patch("/goals/{goal_id}", response_model=GoalOut)
def update_goal(
    goal_id: int,
    payload: GoalUpdate,
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> GoalOut:
    goal = db.get(Goal, goal_id)
    if goal is None or goal.family_id != current.family_id:
        raise _not_found("目标不存在")
    data = payload.model_dump(exclude_unset=True, exclude={"stages"})
    target = goal.target_value or goal.target_points
    if "target_value" in data and data["target_value"] is not None:
        target = data["target_value"]
    if "target_points" in data and data["target_points"] is not None:
        target = data["target_points"]
    stages = payload.stages if "stages" in payload.model_fields_set else None
    if stages is not None:
        _validate_stages(stages, target, goal.progress_mode)
    if "icon_image_path" in data:
        data["icon_image_path"] = _valid_icon_path(data["icon_image_path"], settings)
    if "badge_image_path" in data:
        data["badge_image_path"] = _valid_icon_path(
            data["badge_image_path"], settings
        )
    manual_complete = data.get("status") == GOAL_COMPLETED and goal.status != GOAL_COMPLETED
    reopened = data.get("status") == GOAL_ACTIVE and goal.status == GOAL_COMPLETED
    for key, value in data.items():
        if key in {"target_value", "target_points"}:
            continue
        setattr(goal, key, value)
    if "target_value" in data or "target_points" in data:
        goal.target_value = target
        goal.target_points = target if goal.progress_mode == "points" else 0
    if reopened:
        goal.completed_at = None
    if (
        goal.start_date is not None
        and goal.end_date is not None
        and goal.start_date > goal.end_date
    ):
        raise _bad_request("开始日期不能晚于结束日期")
    if stages is not None:
        _apply_stages(db, goal, stages, settings)
    if manual_complete:
        sync_goal_awards(db, goal, settings, manual_complete=True)
    elif goal.status != "archived":
        sync_goal_awards(db, goal, settings)
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
    settings: Settings = Depends(get_settings),
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
    return [serialize_task(db, task, settings) for task in tasks]


def _check_reward_link(
    db: Session, current: Member, reward_id: int | None
) -> None:
    if reward_id is None:
        return
    reward = db.get(Reward, reward_id)
    if (
        reward is None
        or reward.family_id != current.family_id
        or not reward.active
    ):
        raise _bad_request("关联奖励不存在或已下架")


@router.post("/tasks", response_model=TaskOut)
def create_task(
    payload: TaskCreate,
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
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
    _check_reward_link(db, current, payload.reward_id)
    task = Task(
        family_id=current.family_id,
        child_id=child.id,
        goal_id=payload.goal_id,
        reward_id=payload.reward_id,
        title=payload.title.strip(),
        description=payload.description,
        points=payload.points,
        task_type=payload.task_type,
        requires_photo=payload.requires_photo,
        active_weekdays=weekdays_to_string(payload.active_weekdays),
        streak_threshold_days=payload.streak_threshold_days,
        streak_bonus_percent=payload.streak_bonus_percent,
        active=payload.active,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return serialize_task(db, task, settings)


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
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
    if "reward_id" in data:
        _check_reward_link(db, current, data["reward_id"])
    if "active_weekdays" in data:
        data["active_weekdays"] = weekdays_to_string(data["active_weekdays"])
    for key, value in data.items():
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return serialize_task(db, task, settings)


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
    settings: Settings = Depends(get_settings),
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
            db, submission, current, payload.approve, payload.note, settings
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
        auto_match_percent=payload.auto_match_percent,
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
    if data.get("active") is False or data.get("is_long_term") is False:
        void_matches_for_reward(db, reward.id)
    if data.get("active") is False:
        db.execute(
            update(Task).where(Task.reward_id == reward.id).values(reward_id=None)
        )
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
    void_matches_for_reward(db, reward.id)
    db.execute(update(Task).where(Task.reward_id == reward.id).values(reward_id=None))
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
# Wishes
# ---------------------------------------------------------------------------


@router.get("/wishes", response_model=list[WishOut])
def list_wishes(
    status_filter: str | None = Query(default=None, alias="status"),
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> list[WishOut]:
    stmt = select(Wish)
    if current.role == ROLE_CHILD:
        stmt = stmt.where(Wish.child_id == current.id)
    else:
        stmt = stmt.where(Wish.family_id == current.family_id)
    if status_filter:
        stmt = stmt.where(Wish.status == status_filter)
    rows = db.scalars(stmt.order_by(Wish.created_at.desc())).all()
    return [serialize_wish(db, row) for row in rows]


@router.post("/wishes", response_model=WishOut)
def create_wish_endpoint(
    title: str = Form(...),
    emoji: str = Form(default="🌟"),
    reason: str = Form(default=""),
    expected_points: int = Form(default=0),
    image: UploadFile | None = File(default=None),
    current: Member = Depends(require_child),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> WishOut:
    if len(title) > 100 or len(reason) > 500:
        raise _bad_request("心愿名字或理由太长")
    image_path = _save_icon(image, settings, "wish") if image is not None else None
    try:
        wish = create_wish(
            db,
            current,
            title,
            emoji,
            reason,
            expected_points,
            image_path,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        _remove_photo(image_path, settings)
        raise _bad_request(str(exc))
    db.refresh(wish)
    return serialize_wish(db, wish)


@router.post("/wishes/{wish_id}/list", response_model=WishOut)
def list_wish_endpoint(
    wish_id: int,
    payload: WishListRequest,
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
) -> WishOut:
    wish = db.get(Wish, wish_id)
    if wish is None or wish.family_id != current.family_id:
        raise _not_found("心愿不存在")
    try:
        list_wish_as_reward(db, wish, current, payload)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise _bad_request(str(exc))
    db.refresh(wish)
    return serialize_wish(db, wish)


@router.post("/wishes/{wish_id}/reject", response_model=WishOut)
def reject_wish_endpoint(
    wish_id: int,
    payload: WishRejectRequest,
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
) -> WishOut:
    wish = db.get(Wish, wish_id)
    if wish is None or wish.family_id != current.family_id:
        raise _not_found("心愿不存在")
    try:
        reject_wish(db, wish, current, payload.reason)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise _bad_request(str(exc))
    db.refresh(wish)
    return serialize_wish(db, wish)


# ---------------------------------------------------------------------------
# Parent matching
# ---------------------------------------------------------------------------


@router.get("/matches", response_model=list[WishMatchOut])
def list_matches(
    child_id: int | None = Query(default=None),
    reward_id: int | None = Query(default=None),
    include_closed: bool = Query(default=False),
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> list[WishMatchOut]:
    stmt = select(WishMatch)
    if current.role == ROLE_CHILD:
        stmt = stmt.where(WishMatch.child_id == current.id)
    else:
        stmt = stmt.where(WishMatch.family_id == current.family_id)
        if child_id is not None:
            stmt = stmt.where(
                WishMatch.child_id == resolve_child(db, current, child_id).id
            )
    if reward_id is not None:
        stmt = stmt.where(WishMatch.reward_id == reward_id)
    if not include_closed:
        stmt = stmt.where(WishMatch.status == "active")
    rows = db.scalars(stmt.order_by(WishMatch.created_at.desc())).all()
    return [serialize_match(db, row) for row in rows]


@router.post("/matches", response_model=WishMatchOut)
def create_match_endpoint(
    payload: MatchCreate,
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
) -> WishMatchOut:
    reward = db.get(Reward, payload.reward_id)
    if reward is None or reward.family_id != current.family_id:
        raise _not_found("心愿不存在")
    child = resolve_child(db, current, payload.child_id)
    try:
        match = create_manual_match(
            db, current, child, reward, payload.amount, payload.note
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise _bad_request(str(exc))
    db.refresh(match)
    return serialize_match(db, match)


@router.post("/matches/{match_id}/revoke", response_model=WishMatchOut)
def revoke_match_endpoint(
    match_id: int,
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
) -> WishMatchOut:
    match = db.get(WishMatch, match_id)
    if match is None or match.family_id != current.family_id:
        raise _not_found("配捐记录不存在")
    try:
        revoke_match(db, match)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise _bad_request(str(exc))
    db.refresh(match)
    return serialize_match(db, match)


# ---------------------------------------------------------------------------
# Level configuration
# ---------------------------------------------------------------------------


@router.get("/levels", response_model=LevelConfigOut)
def get_levels(
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> LevelConfigOut:
    thresholds = get_level_thresholds(db, current.family_id)
    return LevelConfigOut(
        thresholds=[
            LevelThresholdOut(level=level, required_points=thresholds[level])
            for level in range(2, MAX_LEVEL + 1)
        ]
    )


@router.put("/levels", response_model=LevelConfigOut)
def update_levels(
    payload: LevelConfigUpdate,
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
) -> LevelConfigOut:
    items = sorted(payload.thresholds, key=lambda item: item.level)
    if [item.level for item in items] != list(range(2, MAX_LEVEL + 1)):
        raise _bad_request("需要配置 Lv.2 到 Lv.20 的等级阈值")
    if items[0].required_points <= 0:
        raise _bad_request("Lv.2 的积分要求必须大于 0")
    for previous, item in zip(items, items[1:]):
        if item.required_points <= previous.required_points:
            raise _bad_request("等级阈值必须严格递增")
    db.execute(
        delete(LevelThreshold).where(
            LevelThreshold.family_id == current.family_id
        )
    )
    db.add_all(
        [
            LevelThreshold(
                family_id=current.family_id,
                level=item.level,
                required_points=item.required_points,
            )
            for item in items
        ]
    )
    db.flush()
    children = db.scalars(
        select(Member).where(
            Member.family_id == current.family_id,
            Member.role == ROLE_CHILD,
        )
    ).all()
    for child in children:
        sync_level_badges(db, child)
    db.commit()
    return get_levels(current, db)


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def _resolve_stats_child(
    db: Session, current: Member, child_id: int | None
) -> Member:
    if current.role == ROLE_CHILD:
        return current
    if child_id is None:
        raise _bad_request("请选择孩子")
    return resolve_child(db, current, child_id)


@router.get("/stats", response_model=StatsOut)
def stats(
    period: str = Query(default="week", pattern="^(week|month|quarter|year)$"),
    child_id: int | None = Query(default=None),
    anchor: date | None = Query(default=None),
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> StatsOut:
    child = _resolve_stats_child(db, current, child_id)
    return build_stats(db, child, period, anchor, settings)


@router.get("/stats/export")
def export_stats(
    period: str = Query(default="week", pattern="^(week|month|quarter|year)$"),
    child_id: int | None = Query(default=None),
    anchor: date | None = Query(default=None),
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    child = _resolve_stats_child(db, current, child_id)
    data = build_stats(db, child, period, anchor, settings)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["心愿罐统计", child.name])
    writer.writerow(["周期", data.label])
    writer.writerow(["开始", data.start_date.isoformat()])
    writer.writerow(["结束", data.end_date.isoformat()])
    writer.writerow([])
    writer.writerow(["任务获得", data.task_points])
    writer.writerow(["连续完成奖励", data.bonus_points])
    writer.writerow(["兑换扣除", data.redeemed_points])
    writer.writerow(["家长调整", data.adjusted_points])
    writer.writerow(["净变化", data.net_points])
    writer.writerow(
        [
            "任务完成率",
            f"{data.task_completion.approved}/{data.task_completion.expected}",
            f"{data.task_completion.percent}%",
        ]
    )
    writer.writerow(["兑换次数", data.redemption_count])
    writer.writerow(["兑换消耗积分", data.redemption_points])
    writer.writerow([])
    writer.writerow(
        ["区间", "任务获得", "连续奖励", "兑换扣除", "家长调整", "净变化"]
    )
    for bucket in data.buckets:
        writer.writerow(
            [
                bucket.label,
                bucket.task_points,
                bucket.bonus_points,
                bucket.redeemed_points,
                bucket.adjusted_points,
                bucket.net_points,
            ]
        )
    content = "﻿" + buffer.getvalue()
    filename = f"wishjar-stats-{data.period}-{data.start_date}.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


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
