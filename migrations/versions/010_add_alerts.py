"""Add alert rules and events tables

Revision ID: 010_add_alerts
Revises: 009_add_scheduling
Create Date: 2026-01-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '010_add_alerts'
down_revision: Union[str, None] = '009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'alert_rules',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False, unique=True),
        sa.Column('description', sa.String(1000), nullable=False, server_default=''),
        sa.Column('metric_name', sa.String(100), nullable=False),
        sa.Column('condition', sa.String(50), nullable=False),
        sa.Column('threshold', sa.Float(), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False, server_default='warning'),
        sa.Column('webhook_url', sa.String(2000), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('cooldown_seconds', sa.Integer(), nullable=False, server_default='300'),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('last_triggered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    op.create_index('ix_alert_rules_metric_name', 'alert_rules', ['metric_name'])
    op.create_index('ix_alert_rules_enabled', 'alert_rules', ['enabled'])
    op.create_index('ix_alert_rules_status', 'alert_rules', ['status'])

    op.create_table(
        'alert_events',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('rule_id', sa.UUID(), nullable=False),
        sa.Column('rule_name', sa.String(200), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('metric_name', sa.String(100), nullable=False),
        sa.Column('metric_value', sa.Float(), nullable=False),
        sa.Column('threshold', sa.Float(), nullable=False),
        sa.Column('condition', sa.String(50), nullable=False),
        sa.Column('message', sa.String(2000), nullable=False),
        sa.Column('webhook_url', sa.String(2000), nullable=False),
        sa.Column('webhook_status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('webhook_response', sa.Text(), nullable=True),
        sa.Column('triggered_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index('ix_alert_events_rule_id', 'alert_events', ['rule_id'])
    op.create_index('ix_alert_events_triggered_at', 'alert_events', ['triggered_at'])
    op.create_index('ix_alert_events_severity', 'alert_events', ['severity'])


def downgrade() -> None:
    op.drop_index('ix_alert_events_severity', table_name='alert_events')
    op.drop_index('ix_alert_events_triggered_at', table_name='alert_events')
    op.drop_index('ix_alert_events_rule_id', table_name='alert_events')
    op.drop_table('alert_events')

    op.drop_index('ix_alert_rules_status', table_name='alert_rules')
    op.drop_index('ix_alert_rules_enabled', table_name='alert_rules')
    op.drop_index('ix_alert_rules_metric_name', table_name='alert_rules')
    op.drop_table('alert_rules')

