from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '008'
down_revision: Union[str, None] = '007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'template_candidates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pattern', sa.String(length=500), nullable=False),
        sa.Column('example_input', sa.Text(), nullable=False),
        sa.Column('generated_commands', postgresql.JSONB(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('frequency', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, default='pending'),
        sa.Column('source_task_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['source_task_id'], ['tasks.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_template_candidates_pattern', 'template_candidates', ['pattern'])
    op.create_index('ix_template_candidates_status', 'template_candidates', ['status'])
    op.create_index('ix_template_candidates_frequency', 'template_candidates', ['frequency'], postgresql_using='btree')


def downgrade() -> None:
    op.drop_index('ix_template_candidates_frequency', table_name='template_candidates')
    op.drop_index('ix_template_candidates_status', table_name='template_candidates')
    op.drop_index('ix_template_candidates_pattern', table_name='template_candidates')
    op.drop_table('template_candidates')
