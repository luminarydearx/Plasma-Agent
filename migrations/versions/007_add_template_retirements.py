from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'template_retirements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_name', sa.String(length=255), nullable=False),
        sa.Column('pattern', sa.Text(), nullable=True),
        sa.Column('reason', sa.String(length=100), nullable=False),
        sa.Column('success_rate', sa.Float(), nullable=False),
        sa.Column('total_uses', sa.Integer(), nullable=False),
        sa.Column('avg_execution_time_ms', sa.Float(), nullable=True),
        sa.Column('retired_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_template_retirements_template_name', 'template_retirements', ['template_name'])
    op.create_index('ix_template_retirements_retired_at', 'template_retirements', ['retired_at'])
    op.create_index('ix_template_retirements_reason', 'template_retirements', ['reason'])

def downgrade() -> None:
    op.drop_index('ix_template_retirements_reason', table_name='template_retirements')
    op.drop_index('ix_template_retirements_retired_at', table_name='template_retirements')
    op.drop_index('ix_template_retirements_template_name', table_name='template_retirements')
    op.drop_table('template_retirements')
