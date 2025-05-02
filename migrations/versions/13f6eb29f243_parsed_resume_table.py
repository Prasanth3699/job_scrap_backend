"""parsed_resume table

Revision ID: 13f6eb29f243
Revises: 3373459191cd
Create Date: 2025-05-01 00:50:36.949848

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '13f6eb29f243'
down_revision: Union[str, None] = '3373459191cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
