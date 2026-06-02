from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("payload", sa.JSON(), nullable=True),
    )
    op.add_column(
        "task_steps",
        sa.Column("exit_code", sa.Integer(), nullable=True),
    )
    op.add_column(
        "task_steps",
        sa.Column("stderr", sa.Text(), nullable=True),
    )
    op.add_column(
        "task_steps",
        sa.Column("duration_ms", sa.Integer(), nullable=True),
    )
    op.create_index("idx_execution_logs_step_id", "execution_logs", ["step_id"])
    op.create_index(
        "idx_execution_logs_timestamp",
        "execution_logs",
        ["timestamp"],
    )
    op.create_index(
        "idx_telemetry_timestamp",
        "telemetry",
        ["timestamp"],
    )


def downgrade() -> None:
    op.drop_index("idx_telemetry_timestamp", table_name="telemetry")
    op.drop_index("idx_execution_logs_timestamp", table_name="execution_logs")
    op.drop_index("idx_execution_logs_step_id", table_name="execution_logs")
    op.drop_column("task_steps", "duration_ms")
    op.drop_column("task_steps", "stderr")
    op.drop_column("task_steps", "exit_code")
    op.drop_column("tasks", "payload")
