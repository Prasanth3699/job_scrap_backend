"""merge proxy table branches

Revision ID: 2a671be92bac
Revises: 09194e700517, 182c9091a6e3, 64c0bbf47583
Create Date: 2025-05-01 00:48:18.075617

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a671be92bac'
down_revision: Union[str, None] = ('09194e700517', '182c9091a6e3', '64c0bbf47583')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
