from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('tasks', sa.Column('cron_expression', sa.String(100), nullable=True))
    op.add_column('tasks', sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('tasks', sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('tasks', sa.Column('is_scheduled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('tasks', sa.Column('schedule_timezone', sa.String(50), nullable=True))
    op.add_column('tasks', sa.Column('missed_run_policy', sa.String(20), nullable=False, server_default='skip'))
    
    op.create_index('idx_tasks_scheduled', 'tasks', ['is_scheduled', 'next_run_at'], postgresql_where=sa.text('is_scheduled = true'))
    op.create_index('idx_tasks_next_run', 'tasks', ['next_run_at'], postgresql_where=sa.text('is_scheduled = true'))


def downgrade() -> None:
    op.drop_index('idx_tasks_next_run', table_name='tasks')
    op.drop_index('idx_tasks_scheduled', table_name='tasks')
    
    op.drop_column('tasks', 'missed_run_policy')
    op.drop_column('tasks', 'schedule_timezone')
    op.drop_column('tasks', 'is_scheduled')
    op.drop_column('tasks', 'last_run_at')
    op.drop_column('tasks', 'next_run_at')
    op.drop_column('tasks', 'cron_expression')
