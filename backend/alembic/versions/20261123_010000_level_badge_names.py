"""Level badge names

Revision ID: 20261123_010000
Revises: 20261122_150000
Create Date: 2026-11-23 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261123_010000"
down_revision: Union[str, None] = "20261122_150000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LEVEL_NAMES = {
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


def _update_names(names: dict[int, str]) -> None:
    bind = op.get_bind()
    statement = sa.text(
        "UPDATE child_badges SET name = :name "
        "WHERE kind = 'level' AND level = :level"
    )
    for level, name in names.items():
        bind.execute(statement, {"name": name, "level": level})


def upgrade() -> None:
    _update_names(LEVEL_NAMES)


def downgrade() -> None:
    _update_names({level: f"Lv.{level} 徽章" for level in LEVEL_NAMES})
