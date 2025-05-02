"""parsed_resume table

Revision ID: 3373459191cd
Revises: 2a671be92bac
Create Date: 2025-05-01 00:49:01.814265

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3373459191cd'
down_revision: Union[str, None] = '2a671be92bac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
