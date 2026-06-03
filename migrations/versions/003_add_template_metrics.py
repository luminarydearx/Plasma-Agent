from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "template_metrics",
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("template_name", sa.String(length=255), nullable=False),
        sa.Column("pattern", sa.String(length=500), nullable=False),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_confidence", sa.Numeric(precision=5, scale=4), nullable=False, server_default="0.0000"),
        sa.Column("total_generation_time_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_name", "pattern", name="uq_template_pattern"),
    )

    op.create_index(
        "ix_template_metrics_template_name",
        "template_metrics",
        ["template_name"],
        unique=False,
    )
    op.create_index(
        "ix_template_metrics_pattern",
        "template_metrics",
        ["pattern"],
        unique=False,
    )
    op.create_index(
        "ix_template_metrics_usage_count",
        "template_metrics",
        ["usage_count"],
        unique=False,
    )
    op.create_index(
        "ix_template_metrics_avg_confidence",
        "template_metrics",
        ["avg_confidence"],
        unique=False,
    )
    op.create_index(
        "ix_template_metrics_last_used_at",
        "template_metrics",
        ["last_used_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_template_metrics_last_used_at", table_name="template_metrics")
    op.drop_index("ix_template_metrics_avg_confidence", table_name="template_metrics")
    op.drop_index("ix_template_metrics_usage_count", table_name="template_metrics")
    op.drop_index("ix_template_metrics_pattern", table_name="template_metrics")
    op.drop_index("ix_template_metrics_template_name", table_name="template_metrics")
    op.drop_table("template_metrics")
