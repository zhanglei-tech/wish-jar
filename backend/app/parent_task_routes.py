from contextlib import contextmanager

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from . import parent_tasks
from .auth import get_db, get_settings, require_child, require_parent
from .config import Settings
from .models import Member
from .schemas import ParentTaskCreate, ParentTaskOut, ParentTaskSubmissionCreate, ParentTaskSubmissionOut, ParentTaskUpdate

router = APIRouter(tags=["parent tasks"])


@contextmanager
def _handle(db: Session, writer: Member | None = None):
    try:
        if writer is not None:
            parent_tasks.begin_write(db, writer)
        yield
        if writer is not None:
            db.commit()
    except parent_tasks.ParentTaskError as error:
        db.rollback()
        raise HTTPException(error.status_code, detail=str(error)) from error
    except Exception:
        db.rollback()
        raise


@router.get("/parent-tasks", response_model=list[ParentTaskOut])
def list_parent_tasks(
    child_id: int | None = None,
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
):
    with _handle(db):
        return parent_tasks.list_tasks(db, current.family_id, child_id)


@router.post("/parent-tasks", response_model=ParentTaskOut, status_code=201)
def create_parent_task(
    payload: ParentTaskCreate,
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
):
    with _handle(db, current):
        return parent_tasks.create_task(db, current, payload)


@router.patch("/parent-tasks/{task_id}", response_model=ParentTaskOut)
def update_parent_task(
    task_id: int,
    payload: ParentTaskUpdate,
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
):
    with _handle(db, current):
        return parent_tasks.update_task(db, current, task_id, payload)


@router.post("/parent-tasks/{task_id}/submissions", response_model=ParentTaskSubmissionOut, status_code=201)
def submit_parent_task(
    task_id: int,
    payload: ParentTaskSubmissionCreate,
    current: Member = Depends(require_parent),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    with _handle(db, current):
        return parent_tasks.submit(db, current, task_id, payload.note, settings)


@router.post("/parent-tasks/{task_id}/reminders", status_code=204)
def remind_parent_task(
    task_id: int,
    current: Member = Depends(require_child),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    with _handle(db, current):
        parent_tasks.remind(db, current, task_id, settings)
    return Response(status_code=204)


@router.patch("/parent-task-submissions/{submission_id}/confirmation", response_model=ParentTaskSubmissionOut)
def confirm_parent_task(
    submission_id: int,
    current: Member = Depends(require_child),
    db: Session = Depends(get_db),
):
    with _handle(db, current):
        return parent_tasks.confirm(db, current, submission_id)
