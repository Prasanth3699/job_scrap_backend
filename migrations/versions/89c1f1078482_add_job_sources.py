"""add job sources

Revision ID: 89c1f1078482
Revises: 3c02d630c25b
Create Date: 2025-03-01 18:28:20.517596

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '89c1f1078482'
down_revision: Union[str, None] = '3c02d630c25b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
