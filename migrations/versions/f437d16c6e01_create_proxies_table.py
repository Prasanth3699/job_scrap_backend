"""create proxies table

Revision ID: f437d16c6e01
Revises: 13f6eb29f243
Create Date: 2025-05-01 01:01:37.852609

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f437d16c6e01"
down_revision: Union[str, None] = "13f6eb29f243"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "proxies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ip", sa.String(length=50), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column(
            "protocol",
            sa.Enum("HTTP", "HTTPS", "SOCKS4", "SOCKS5", name="proxyprotocol"),
            nullable=False,
        ),
        sa.Column(
            "anonymity",
            sa.Enum(
                "TRANSPARENT", "ANONYMOUS", "HIGH_ANONYMITY", name="anonymitylevel"
            ),
            nullable=False,
        ),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("total_requests", sa.Integer(), nullable=True),
        sa.Column("successful_requests", sa.Integer(), nullable=True),
        sa.Column("failed_requests", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.Column("supports_ssl", sa.Boolean(), nullable=True),
        sa.Column("supports_streaming", sa.Boolean(), nullable=True),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("source_type", sa.String(), nullable=True),
        sa.Column("reliability_score", sa.Float(), nullable=True),
        sa.Column("performance_score", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("proxies")
