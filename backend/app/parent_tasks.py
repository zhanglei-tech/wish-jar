from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .config import Settings
from .constants import ROLE_CHILD, ROLE_PARENT, TASK_DAILY
from .models import Member, ParentTask, ParentTaskReminder, ParentTaskSubmission
from .schemas import ParentTaskCard, ParentTaskCreate, ParentTaskOut, ParentTaskSubmissionOut, ParentTaskUpdate
from .services import _create_transaction, parse_weekdays, weekdays_to_string
from .timeutils import as_utc, period_key, to_local, utcnow


class ParentTaskError(ValueError):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def begin_write(db: Session, actor: Member) -> None:
    # In sqlite3's legacy transaction mode, the auth SELECT has not begun a write transaction.
    connection = db.connection()
    if connection.dialect.name == "sqlite":
        connection.exec_driver_sql("BEGIN IMMEDIATE")
    db.refresh(actor)
    if not actor.is_active:
        raise ParentTaskError(401, "登录状态无效")


def _member(db: Session, member_id: int, family_id: int, role: str) -> Member | None:
    member = db.get(Member, member_id)
    return member if member and member.family_id == family_id and member.role == role else None


def serialize_task(db: Session, task: ParentTask) -> ParentTaskOut:
    parent = _member(db, task.assigned_parent_id, task.family_id, ROLE_PARENT)
    child = _member(db, task.child_id, task.family_id, ROLE_CHILD)
    return ParentTaskOut(
        id=task.id, child_id=task.child_id, assigned_parent_id=task.assigned_parent_id,
        title=task.title, description=task.description, points=task.points,
        task_type=task.task_type, active_weekdays=parse_weekdays(task.active_weekdays),
        active=task.active, child_name=child.name if child else "",
        assigned_parent_name=parent.name if parent else "",
    )


def serialize_submission(db: Session, row: ParentTaskSubmission, family_id: int) -> ParentTaskSubmissionOut:
    parent = _member(db, row.assigned_parent_id, family_id, ROLE_PARENT)
    return ParentTaskSubmissionOut(
        id=row.id, task_id=row.task_id, task_title=row.task_title, child_id=row.child_id,
        assigned_parent_id=row.assigned_parent_id, assigned_parent_name=parent.name if parent else "",
        points=row.points, note=row.note, period_key=row.period_key,
        submitted_at=as_utc(row.submitted_at), confirmed_at=as_utc(row.confirmed_at),
    )


def list_tasks(db: Session, family_id: int, child_id: int | None) -> list[ParentTaskOut]:
    query = select(ParentTask).where(ParentTask.family_id == family_id)
    if child_id is not None:
        if not _member(db, child_id, family_id, ROLE_CHILD):
            raise ParentTaskError(404, "孩子不存在")
        query = query.where(ParentTask.child_id == child_id)
    return [serialize_task(db, task) for task in db.scalars(query.order_by(ParentTask.id.desc()))]


def _get_task(db: Session, task_id: int, family_id: int) -> ParentTask:
    task = db.get(ParentTask, task_id)
    if not task or task.family_id != family_id:
        raise ParentTaskError(404, "家长任务不存在")
    return task


def create_task(db: Session, parent: Member, payload: ParentTaskCreate) -> ParentTaskOut:
    child = _member(db, payload.child_id, parent.family_id, ROLE_CHILD)
    assignee = _member(db, payload.assigned_parent_id, parent.family_id, ROLE_PARENT)
    if not child or not child.is_active:
        raise ParentTaskError(400, "请选择同家庭启用的孩子")
    if not assignee or not assignee.is_active:
        raise ParentTaskError(400, "请选择同家庭启用的家长")
    task = ParentTask(**payload.model_dump(exclude={"active_weekdays"}),
                      family_id=parent.family_id,
                      active_weekdays=weekdays_to_string(payload.active_weekdays))
    db.add(task)
    db.flush()
    return serialize_task(db, task)


def update_task(db: Session, parent: Member, task_id: int, payload: ParentTaskUpdate) -> ParentTaskOut:
    task = _get_task(db, task_id, parent.family_id)
    data = payload.model_dump(exclude_none=True)
    if payload.active_weekdays is not None:
        data["active_weekdays"] = weekdays_to_string(payload.active_weekdays)
    for key, value in data.items():
        setattr(task, key, value)
    return serialize_task(db, task)


def _applies(task: ParentTask, settings: Settings, now: datetime) -> bool:
    return task.task_type != TASK_DAILY or to_local(now, settings).isoweekday() in parse_weekdays(task.active_weekdays)


def _active_members(db: Session, task: ParentTask) -> bool:
    parent = _member(db, task.assigned_parent_id, task.family_id, ROLE_PARENT)
    child = _member(db, task.child_id, task.family_id, ROLE_CHILD)
    return bool(parent and parent.is_active and child and child.is_active)


def _open_period(db: Session, task: ParentTask, settings: Settings, now: datetime) -> str:
    if not task.active or not _active_members(db, task):
        raise ParentTaskError(409, "该家长任务不可用")
    if not _applies(task, settings, now):
        raise ParentTaskError(409, "今天不是这个任务的适用日")
    key = period_key(task.task_type, settings, now)
    existing = db.scalar(select(ParentTaskSubmission.id).where(
        ParentTaskSubmission.task_id == task.id, ParentTaskSubmission.period_key == key,
    ))
    if existing is not None:
        raise ParentTaskError(409, "该任务本周期已打卡")
    return key


def submit(db: Session, parent: Member, task_id: int, note: str, settings: Settings) -> ParentTaskSubmissionOut:
    task = _get_task(db, task_id, parent.family_id)
    if task.assigned_parent_id != parent.id:
        raise ParentTaskError(403, "只有执行家长可以打卡")
    now = utcnow()
    key = _open_period(db, task, settings, now)
    row = ParentTaskSubmission(
        task_id=task.id, child_id=task.child_id, assigned_parent_id=parent.id,
        task_title=task.title, points=task.points, note=note.strip(), period_key=key, submitted_at=now,
    )
    db.add(row)
    db.flush()
    return serialize_submission(db, row, parent.family_id)


def remind(db: Session, child: Member, task_id: int, settings: Settings) -> None:
    task = _get_task(db, task_id, child.family_id)
    if task.child_id != child.id:
        raise ParentTaskError(403, "只有受益孩子可以提醒")
    now = utcnow()
    key = _open_period(db, task, settings, now)
    existing = db.scalar(select(ParentTaskReminder.id).where(
        ParentTaskReminder.task_id == task.id, ParentTaskReminder.period_key == key,
    ))
    if existing is None:
        db.add(ParentTaskReminder(task_id=task.id, period_key=key, created_at=now))


def confirm(db: Session, child: Member, submission_id: int) -> ParentTaskSubmissionOut:
    row = db.get(ParentTaskSubmission, submission_id)
    if row is None:
        raise ParentTaskError(404, "打卡不存在")
    _get_task(db, row.task_id, child.family_id)
    if row.child_id != child.id:
        raise ParentTaskError(403, "只有受益孩子可以确认")
    now = utcnow()
    result = db.execute(update(ParentTaskSubmission).where(
        ParentTaskSubmission.id == row.id, ParentTaskSubmission.child_id == child.id,
        ParentTaskSubmission.confirmed_at.is_(None),
    ).values(confirmed_at=now, confirmed_by_id=child.id))
    if result.rowcount != 1:
        raise ParentTaskError(409, "这条打卡已确认")
    _create_transaction(
        db, child.family_id, child.id, row.points, "parent_task", f"完成家长任务：{row.task_title}",
        ref_type="parent_task_submission", ref_id=row.id, created_at=now,
    )
    return serialize_submission(db, row, child.family_id)


def current_cards(db: Session, actor: Member, settings: Settings) -> list[ParentTaskCard]:
    is_parent = actor.role == ROLE_PARENT
    owner = ParentTask.assigned_parent_id if is_parent else ParentTask.child_id
    tasks = db.scalars(select(ParentTask).where(
        ParentTask.family_id == actor.family_id, ParentTask.active.is_(True), owner == actor.id,
    ).order_by(ParentTask.id)).all()
    now = utcnow()
    cards = []
    for task in tasks:
        if not _applies(task, settings, now) or not _active_members(db, task):
            continue
        key = period_key(task.task_type, settings, now)
        submission = db.scalar(select(ParentTaskSubmission).where(
            ParentTaskSubmission.task_id == task.id, ParentTaskSubmission.period_key == key,
        ))
        if submission and submission.confirmed_at and key == "once":
            continue
        reminded = submission is None and db.scalar(select(ParentTaskReminder.id).where(
            ParentTaskReminder.task_id == task.id, ParentTaskReminder.period_key == key,
        )) is not None
        cards.append(ParentTaskCard(
            task=serialize_task(db, task), period_key=key, reminded=reminded,
            status="todo" if submission is None else "done" if submission.confirmed_at else "pending",
        ))
    return cards


def pending_confirmations(db: Session, child: Member) -> list[ParentTaskSubmissionOut]:
    rows = db.scalars(select(ParentTaskSubmission).join(ParentTask).where(
        ParentTask.family_id == child.family_id, ParentTaskSubmission.child_id == child.id,
        ParentTaskSubmission.confirmed_at.is_(None),
    ).order_by(ParentTaskSubmission.submitted_at, ParentTaskSubmission.id))
    return [serialize_submission(db, row, child.family_id) for row in rows]
