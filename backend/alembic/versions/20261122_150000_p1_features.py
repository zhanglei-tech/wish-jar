"""P1 features

Revision ID: 20261122_150000
Revises: 163079689374
Create Date: 2026-11-22 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261122_150000"
down_revision: Union[str, None] = "163079689374"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("goals", schema=None) as batch_op:
        batch_op.add_column(sa.Column("icon_image_path", sa.String(length=500), nullable=True))
        batch_op.add_column(
            sa.Column("progress_mode", sa.String(length=20), nullable=False, server_default="points")
        )
        batch_op.add_column(
            sa.Column("target_value", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("badge_name", sa.String(length=100), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("badge_emoji", sa.String(length=16), nullable=False, server_default="")
        )
        batch_op.add_column(sa.Column("badge_image_path", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))

    op.execute("UPDATE goals SET target_value = target_points")

    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("reward_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "active_weekdays",
                sa.String(length=20),
                nullable=False,
                server_default="1,2,3,4,5,6,7",
            )
        )
        batch_op.add_column(
            sa.Column("streak_threshold_days", sa.Integer(), nullable=False, server_default="7")
        )
        batch_op.add_column(
            sa.Column("streak_bonus_percent", sa.Integer(), nullable=False, server_default="25")
        )
        batch_op.create_index(batch_op.f("ix_tasks_reward_id"), ["reward_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_tasks_reward_id_rewards",
            "rewards",
            ["reward_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("submissions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("bonus_points", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("bonus_percent", sa.Integer(), nullable=False, server_default="0")
        )

    with op.batch_alter_table("rewards", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("auto_match_percent", sa.Integer(), nullable=False, server_default="0")
        )

    op.create_table(
        "level_thresholds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("family_id", sa.Integer(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("required_points", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("family_id", "level", name="uq_level_threshold_family"),
    )
    with op.batch_alter_table("level_thresholds", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_level_thresholds_family_id"), ["family_id"], unique=False
        )

    op.create_table(
        "goal_stages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("goal_id", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("threshold_value", sa.Integer(), nullable=False),
        sa.Column("badge_name", sa.String(length=100), nullable=False),
        sa.Column("badge_emoji", sa.String(length=16), nullable=False),
        sa.Column("badge_image_path", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("goal_id", "sort_order", name="uq_goal_stage_order"),
    )
    with op.batch_alter_table("goal_stages", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_goal_stages_goal_id"), ["goal_id"], unique=False)

    op.create_table(
        "child_badges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("family_id", sa.Integer(), nullable=False),
        sa.Column("child_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("level", sa.Integer(), nullable=True),
        sa.Column("goal_id", sa.Integer(), nullable=True),
        sa.Column("goal_stage_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("emoji", sa.String(length=16), nullable=False),
        sa.Column("image_path", sa.String(length=500), nullable=True),
        sa.Column("awarded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["goal_stage_id"], ["goal_stages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("child_id", "kind", "level", name="uq_child_badge_level"),
        sa.UniqueConstraint("child_id", "goal_stage_id", name="uq_child_badge_stage"),
    )
    with op.batch_alter_table("child_badges", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_child_badges_child_id"), ["child_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_child_badges_family_id"), ["family_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_child_badges_goal_id"), ["goal_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_child_badges_goal_stage_id"), ["goal_stage_id"], unique=False
        )
        batch_op.create_index(
            "ix_child_badges_child_awarded", ["child_id", "awarded_at"], unique=False
        )

    op.create_table(
        "wishes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("family_id", sa.Integer(), nullable=False),
        sa.Column("child_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("emoji", sa.String(length=16), nullable=False),
        sa.Column("image_path", sa.String(length=500), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("expected_points", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reward_id", sa.Integer(), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=False),
        sa.Column("reviewed_by_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["reward_id"], ["rewards.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("wishes", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_wishes_child_id"), ["child_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_wishes_family_id"), ["family_id"], unique=False)
        batch_op.create_index("ix_wishes_child_status", ["child_id", "status"], unique=False)

    op.create_table(
        "wish_matches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("family_id", sa.Integer(), nullable=False),
        sa.Column("child_id", sa.Integer(), nullable=False),
        sa.Column("reward_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("used_amount", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("ratio_snapshot", sa.Integer(), nullable=True),
        sa.Column("redemption_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["child_id"], ["members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["redemption_id"], ["redemptions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reward_id"], ["rewards.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("wish_matches", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_wish_matches_child_id"), ["child_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_wish_matches_family_id"), ["family_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_wish_matches_reward_id"), ["reward_id"], unique=False)
        batch_op.create_index(
            "ix_wish_matches_reward_status", ["reward_id", "status"], unique=False
        )
        batch_op.create_index(
            "ix_wish_matches_child_status", ["child_id", "status"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("wish_matches", schema=None) as batch_op:
        batch_op.drop_index("ix_wish_matches_child_status")
        batch_op.drop_index("ix_wish_matches_reward_status")
        batch_op.drop_index(batch_op.f("ix_wish_matches_reward_id"))
        batch_op.drop_index(batch_op.f("ix_wish_matches_family_id"))
        batch_op.drop_index(batch_op.f("ix_wish_matches_child_id"))
    op.drop_table("wish_matches")

    with op.batch_alter_table("wishes", schema=None) as batch_op:
        batch_op.drop_index("ix_wishes_child_status")
        batch_op.drop_index(batch_op.f("ix_wishes_family_id"))
        batch_op.drop_index(batch_op.f("ix_wishes_child_id"))
    op.drop_table("wishes")

    with op.batch_alter_table("child_badges", schema=None) as batch_op:
        batch_op.drop_index("ix_child_badges_child_awarded")
        batch_op.drop_index(batch_op.f("ix_child_badges_goal_stage_id"))
        batch_op.drop_index(batch_op.f("ix_child_badges_goal_id"))
        batch_op.drop_index(batch_op.f("ix_child_badges_family_id"))
        batch_op.drop_index(batch_op.f("ix_child_badges_child_id"))
    op.drop_table("child_badges")

    with op.batch_alter_table("goal_stages", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_goal_stages_goal_id"))
    op.drop_table("goal_stages")

    with op.batch_alter_table("level_thresholds", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_level_thresholds_family_id"))
    op.drop_table("level_thresholds")

    with op.batch_alter_table("rewards", schema=None) as batch_op:
        batch_op.drop_column("auto_match_percent")

    with op.batch_alter_table("submissions", schema=None) as batch_op:
        batch_op.drop_column("bonus_percent")
        batch_op.drop_column("bonus_points")

    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_constraint("fk_tasks_reward_id_rewards", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_tasks_reward_id"))
        batch_op.drop_column("streak_bonus_percent")
        batch_op.drop_column("streak_threshold_days")
        batch_op.drop_column("active_weekdays")
        batch_op.drop_column("reward_id")

    with op.batch_alter_table("goals", schema=None) as batch_op:
        batch_op.drop_column("completed_at")
        batch_op.drop_column("badge_image_path")
        batch_op.drop_column("badge_emoji")
        batch_op.drop_column("badge_name")
        batch_op.drop_column("target_value")
        batch_op.drop_column("progress_mode")
        batch_op.drop_column("icon_image_path")
