from alembic import op
import sqlalchemy as sa

revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'memories',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('memory_type', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    
    op.create_index('idx_memories_type', 'memories', ['memory_type'])
    op.create_index('idx_memories_user', 'memories', ['user_id'])
    op.create_index('idx_memories_created', 'memories', ['created_at'])
    
    op.create_table(
        'conversation_sessions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(200), nullable=True),
        sa.Column('message_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    
    op.create_index('idx_sessions_user', 'conversation_sessions', ['user_id'])
    op.create_index('idx_sessions_updated', 'conversation_sessions', ['updated_at'])
    
    op.create_table(
        'conversation_messages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('session_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['conversation_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    
    op.create_index('idx_messages_session', 'conversation_messages', ['session_id'])
    op.create_index('idx_messages_created', 'conversation_messages', ['created_at'])
    op.create_index('idx_messages_user', 'conversation_messages', ['user_id'])
    
    op.create_table(
        'task_patterns',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('task_name', sa.String(200), nullable=False),
        sa.Column('commands', sa.JSON(), nullable=False),
        sa.Column('success_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_duration_ms', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    
    op.create_index('idx_patterns_user', 'task_patterns', ['user_id'])
    op.create_index('idx_patterns_name', 'task_patterns', ['task_name'])
    op.create_index('idx_patterns_confidence', 'task_patterns', [sa.text('confidence DESC')])


def downgrade():
    op.drop_table('task_patterns')
    op.drop_table('conversation_messages')
    op.drop_table('conversation_sessions')
    op.drop_table('memories')
