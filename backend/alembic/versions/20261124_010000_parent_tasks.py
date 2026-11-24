"""Add parent tasks and protect parent task credits from duplication.

Revision ID: 20261124_010000
Revises: 20261123_010000
Create Date: 2026-11-24 01:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261124_010000"
down_revision: Union[str, None] = "20261123_010000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CREDIT_INDEX = "uq_point_transactions_parent_task_submission"


def upgrade() -> None:
    op.create_table(
        "parent_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("family_id", sa.Integer(), sa.ForeignKey("families.id"), nullable=False),
        sa.Column("child_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("assigned_parent_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("task_type", sa.String(20), nullable=False),
        sa.Column("active_weekdays", sa.String(20), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_parent_tasks_family_id", "parent_tasks", ["family_id"])
    op.create_index("ix_parent_tasks_child_id", "parent_tasks", ["child_id"])
    op.create_index("ix_parent_tasks_assigned_parent_id", "parent_tasks", ["assigned_parent_id"])

    op.create_table(
        "parent_task_submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("parent_tasks.id"), nullable=False),
        sa.Column("child_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("assigned_parent_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("task_title", sa.String(100), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("period_key", sa.String(20), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=True),
        sa.UniqueConstraint("task_id", "period_key", name="uq_parent_task_submission_period"),
    )
    op.create_index(
        "ix_parent_task_submissions_child_id", "parent_task_submissions", ["child_id"]
    )

    op.create_table(
        "parent_task_reminders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("parent_tasks.id"), nullable=False),
        sa.Column("period_key", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", "period_key", name="uq_parent_task_reminder_period"),
    )
    op.create_index(
        _CREDIT_INDEX,
        "point_transactions",
        ["ref_id"],
        unique=True,
        sqlite_where=sa.text("kind = 'parent_task' AND ref_type = 'parent_task_submission'"),
    )


def downgrade() -> None:
    if op.get_context().as_sql:
        raise NotImplementedError("Downgrading parent tasks requires checking a live database.")

    bind = op.get_bind()
    checks = (
        "SELECT 1 FROM parent_tasks LIMIT 1",
        "SELECT 1 FROM parent_task_submissions LIMIT 1",
        "SELECT 1 FROM parent_task_reminders LIMIT 1",
        "SELECT 1 FROM point_transactions WHERE kind = 'parent_task' LIMIT 1",
    )
    if any(bind.scalar(sa.text(statement)) is not None for statement in checks):
        raise NotImplementedError("Downgrade would discard parent task data or leave parent task credits unsupported.")

    op.drop_index(_CREDIT_INDEX, table_name="point_transactions")
    op.drop_table("parent_task_reminders")
    op.drop_table("parent_task_submissions")
    op.drop_table("parent_tasks")
