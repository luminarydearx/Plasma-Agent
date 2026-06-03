from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'ab_tests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_name', sa.String(length=255), nullable=False),
        sa.Column('version_a_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version_b_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, default='active'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('winner_version_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('confidence_threshold', sa.Float(), nullable=False, default=0.95),
        sa.Column('min_samples', sa.Integer(), nullable=False, default=100),
        sa.ForeignKeyConstraint(['version_a_id'], ['template_versions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['version_b_id'], ['template_versions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['winner_version_id'], ['template_versions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ab_tests_template_name', 'ab_tests', ['template_name'])
    op.create_index('ix_ab_tests_status', 'ab_tests', ['status'])
    
    op.create_table(
        'ab_test_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ab_test_id', sa.Integer(), nullable=False),
        sa.Column('version_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('execution_time_ms', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['ab_test_id'], ['ab_tests.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['version_id'], ['template_versions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ab_test_results_ab_test_id', 'ab_test_results', ['ab_test_id'])
    op.create_index('ix_ab_test_results_version_id', 'ab_test_results', ['version_id'])

def downgrade() -> None:
    op.drop_index('ix_ab_test_results_version_id', table_name='ab_test_results')
    op.drop_index('ix_ab_test_results_ab_test_id', table_name='ab_test_results')
    op.drop_table('ab_test_results')
    op.drop_index('ix_ab_tests_status', table_name='ab_tests')
    op.drop_index('ix_ab_tests_template_name', table_name='ab_tests')
    op.drop_table('ab_tests')
