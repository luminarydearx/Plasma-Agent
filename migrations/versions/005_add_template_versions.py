from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "template_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("commands", postgresql.JSONB(), nullable=False),
        sa.Column("pattern_name", sa.String(length=200), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("change_description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(["template_id"], ["template_metrics.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("template_id", "version_number", name="uq_template_version"),
    )
    op.create_index("ix_template_versions_template_id", "template_versions", ["template_id"])
    op.create_index("ix_template_versions_created_at", "template_versions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_template_versions_created_at", table_name="template_versions")
    op.drop_index("ix_template_versions_template_id", table_name="template_versions")
    op.drop_table("template_versions")
