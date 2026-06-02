"""Initial schema with pgvector

Revision ID: 001
Revises:
Create Date: 2026-06-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Note: pgvector extension requires separate installation
    # Skip for now as it's not available on this PostgreSQL instance
    # Will be enabled in Phase 3 when AI integration is implemented
    
    # Create tasks table
    op.create_table(
        'tasks',
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='PENDING'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_tasks_status', 'tasks', ['status'])

    # Create task_steps table
    op.create_table(
        'task_steps',
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('task_id', sa.Uuid(), nullable=False),
        sa.Column('step_order', sa.Integer(), nullable=False),
        sa.Column('command', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='PENDING'),
        sa.Column('output', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('task_id', 'step_order')
    )
    op.create_index('idx_task_steps_task_id', 'task_steps', ['task_id'])

    # Create execution_logs table
    op.create_table(
        'execution_logs',
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('task_id', sa.Uuid(), nullable=False),
        sa.Column('step_id', sa.Uuid(), nullable=True),
        sa.Column('log_level', sa.String(length=20), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['step_id'], ['task_steps.id'], ondelete='CASCADE')
    )
    op.create_index('idx_execution_logs_task_id', 'execution_logs', ['task_id'])

    # Create telemetry table
    op.create_table(
        'telemetry',
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_telemetry_event_type', 'telemetry', ['event_type'])


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_index('idx_telemetry_event_type', table_name='telemetry')
    op.drop_table('telemetry')
    
    op.drop_index('idx_execution_logs_task_id', table_name='execution_logs')
    op.drop_table('execution_logs')
    
    op.drop_index('idx_task_steps_task_id', table_name='task_steps')
    op.drop_table('task_steps')
    
    op.drop_index('idx_tasks_status', table_name='tasks')
    op.drop_table('tasks')
    
    # Note: We don't drop the vector extension as it might be used by other databases
