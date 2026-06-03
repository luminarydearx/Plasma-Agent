from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "template_metrics",
        "avg_confidence",
        type_=sa.Numeric(precision=5, scale=4),
        postgresql_using="avg_confidence::numeric(5,4)",
        existing_type=sa.Numeric(precision=3, scale=2),
        existing_nullable=False,
        existing_server_default="0.00",
        server_default="0.0000",
    )

    op.drop_index("idx_template_metrics_template_name", table_name="template_metrics")

    op.create_unique_constraint(
        "uq_template_pattern",
        "template_metrics",
        ["template_name", "pattern"],
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
        "ix_template_metrics_avg_confidence",
        "template_metrics",
        ["avg_confidence"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_template_metrics_avg_confidence", table_name="template_metrics")
    op.drop_index("ix_template_metrics_pattern", table_name="template_metrics")
    op.drop_index("ix_template_metrics_template_name", table_name="template_metrics")

    op.drop_constraint("uq_template_pattern", "template_metrics", type_="unique")

    op.create_index(
        "idx_template_metrics_template_name",
        "template_metrics",
        ["template_name"],
        unique=True,
    )

    op.alter_column(
        "template_metrics",
        "avg_confidence",
        type_=sa.Numeric(precision=3, scale=2),
        postgresql_using="avg_confidence::numeric(3,2)",
        existing_type=sa.Numeric(precision=5, scale=4),
        existing_nullable=False,
        existing_server_default="0.0000",
        server_default="0.00",
    )
