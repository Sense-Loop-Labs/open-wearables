"""Add instruction template tables

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add timezone column to sl_patient
    op.add_column(
        'sl_patient',
        sa.Column('timezone', sa.String(50), nullable=False, server_default='America/New_York')
    )

    # Create sl_activity_template table
    op.create_table(
        'sl_activity_template',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='draft'),
        sa.Column('version', sa.String(50), nullable=False, server_default='1.0.0'),
        sa.Column('category_code', sa.String(50), nullable=False),
        sa.Column('kind', sa.String(50), nullable=False, server_default='task'),
        sa.Column('completion_method', sa.String(50), nullable=False, server_default='manual'),
        sa.Column('data_trigger_types', postgresql.ARRAY(sa.String(100)), nullable=True),
        sa.Column('data_threshold', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('confirmation_prompt', sa.String(255), nullable=True),
        sa.Column('content', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('default_timing', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('code_system', sa.String(255), nullable=True),
        sa.Column('code_value', sa.String(50), nullable=True),
        sa.Column('created_by_id', sa.UUID(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['sl_organization.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_id'], ['sl_practitioner.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_activity_template_name')
    )
    op.create_index(op.f('ix_sl_activity_template_organization_id'), 'sl_activity_template', ['organization_id'], unique=False)
    op.create_index(op.f('ix_sl_activity_template_category_code'), 'sl_activity_template', ['category_code'], unique=False)
    op.create_index(op.f('ix_sl_activity_template_status'), 'sl_activity_template', ['status'], unique=False)

    # Create sl_instruction_template table
    op.create_table(
        'sl_instruction_template',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='draft'),
        sa.Column('version', sa.String(50), nullable=False, server_default='1.0.0'),
        sa.Column('content', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('notification_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_by_id', sa.UUID(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['sl_organization.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_id'], ['sl_practitioner.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_instruction_template_name')
    )
    op.create_index(op.f('ix_sl_instruction_template_organization_id'), 'sl_instruction_template', ['organization_id'], unique=False)
    op.create_index(op.f('ix_sl_instruction_template_status'), 'sl_instruction_template', ['status'], unique=False)

    # Create sl_instruction_template_health_focus table
    op.create_table(
        'sl_instruction_template_health_focus',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('template_id', sa.UUID(), nullable=False),
        sa.Column('health_focus_code', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['template_id'], ['sl_instruction_template.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('template_id', 'health_focus_code', name='uq_template_health_focus')
    )
    op.create_index(op.f('ix_sl_instruction_template_health_focus_template_id'), 'sl_instruction_template_health_focus', ['template_id'], unique=False)
    op.create_index(op.f('ix_sl_instruction_template_health_focus_code'), 'sl_instruction_template_health_focus', ['health_focus_code'], unique=False)

    # Create sl_patient_instruction_plan table
    op.create_table(
        'sl_patient_instruction_plan',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('patient_id', sa.UUID(), nullable=False),
        sa.Column('template_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('effective_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('effective_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('customizations', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('resolved_content', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('tasks_generated_through', sa.Date(), nullable=True),
        sa.Column('reference_date', sa.Date(), nullable=True),
        sa.Column('reference_type', sa.String(50), nullable=True),
        sa.Column('assigned_by_id', sa.UUID(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['patient_id'], ['sl_patient.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['template_id'], ['sl_instruction_template.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['assigned_by_id'], ['sl_practitioner.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sl_patient_instruction_plan_patient_id'), 'sl_patient_instruction_plan', ['patient_id'], unique=False)
    op.create_index(op.f('ix_sl_patient_instruction_plan_template_id'), 'sl_patient_instruction_plan', ['template_id'], unique=False)
    op.create_index(op.f('ix_sl_patient_instruction_plan_status'), 'sl_patient_instruction_plan', ['status'], unique=False)

    # Create sl_patient_instruction_task table
    op.create_table(
        'sl_patient_instruction_task',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('plan_id', sa.UUID(), nullable=False),
        sa.Column('patient_id', sa.UUID(), nullable=False),
        sa.Column('plan_item_id', sa.String(100), nullable=False),
        sa.Column('section_id', sa.String(100), nullable=True),
        sa.Column('task_type', sa.String(50), nullable=False),
        sa.Column('task_code', sa.String(100), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('completion_method', sa.String(50), nullable=False),
        sa.Column('data_trigger_types', postgresql.ARRAY(sa.String(100)), nullable=True),
        sa.Column('data_threshold', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('confirmation_prompt', sa.String(255), nullable=True),
        sa.Column('scheduled_date', sa.Date(), nullable=False),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('scheduled_time_local', sa.String(50), nullable=True),
        sa.Column('patient_timezone', sa.String(50), nullable=False),
        sa.Column('time_window_minutes', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completion_source', sa.String(50), nullable=True),
        sa.Column('linked_data_type', sa.String(50), nullable=True),
        sa.Column('linked_data_id', sa.UUID(), nullable=True),
        sa.Column('linked_data_value', sa.String(255), nullable=True),
        sa.Column('user_notes', sa.Text(), nullable=True),
        sa.Column('skip_reason', sa.String(255), nullable=True),
        sa.Column('reminder_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('overdue_notification_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_overdue_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('confirmation_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('confirmation_response_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('success_notification_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('snoozed_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('snooze_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['plan_id'], ['sl_patient_instruction_plan.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['sl_patient.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sl_patient_instruction_task_plan_id'), 'sl_patient_instruction_task', ['plan_id'], unique=False)
    op.create_index(op.f('ix_sl_patient_instruction_task_patient_id'), 'sl_patient_instruction_task', ['patient_id'], unique=False)
    op.create_index(op.f('ix_sl_patient_instruction_task_scheduled_date'), 'sl_patient_instruction_task', ['scheduled_date'], unique=False)
    op.create_index(op.f('ix_sl_patient_instruction_task_status'), 'sl_patient_instruction_task', ['status'], unique=False)
    op.create_index('ix_sl_task_patient_date', 'sl_patient_instruction_task', ['patient_id', 'scheduled_date'], unique=False)
    op.create_index('ix_sl_task_status_date', 'sl_patient_instruction_task', ['status', 'scheduled_date'], unique=False)
    op.create_index('ix_sl_task_pending_triggers', 'sl_patient_instruction_task', ['status', 'completion_method', 'scheduled_date'], unique=False)

    # Create sl_task_notification_log table
    op.create_table(
        'sl_task_notification_log',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('task_id', sa.UUID(), nullable=False),
        sa.Column('patient_id', sa.UUID(), nullable=False),
        sa.Column('notification_type', sa.String(50), nullable=False),
        sa.Column('channel', sa.String(50), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failure_reason', sa.String(255), nullable=True),
        sa.Column('response', sa.String(50), nullable=True),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('action_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('external_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['task_id'], ['sl_patient_instruction_task.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['sl_patient.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sl_task_notification_log_task_id'), 'sl_task_notification_log', ['task_id'], unique=False)
    op.create_index(op.f('ix_sl_task_notification_log_patient_id'), 'sl_task_notification_log', ['patient_id'], unique=False)
    op.create_index(op.f('ix_sl_task_notification_log_notification_type'), 'sl_task_notification_log', ['notification_type'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order of creation
    op.drop_index(op.f('ix_sl_task_notification_log_notification_type'), table_name='sl_task_notification_log')
    op.drop_index(op.f('ix_sl_task_notification_log_patient_id'), table_name='sl_task_notification_log')
    op.drop_index(op.f('ix_sl_task_notification_log_task_id'), table_name='sl_task_notification_log')
    op.drop_table('sl_task_notification_log')

    op.drop_index('ix_sl_task_pending_triggers', table_name='sl_patient_instruction_task')
    op.drop_index('ix_sl_task_status_date', table_name='sl_patient_instruction_task')
    op.drop_index('ix_sl_task_patient_date', table_name='sl_patient_instruction_task')
    op.drop_index(op.f('ix_sl_patient_instruction_task_status'), table_name='sl_patient_instruction_task')
    op.drop_index(op.f('ix_sl_patient_instruction_task_scheduled_date'), table_name='sl_patient_instruction_task')
    op.drop_index(op.f('ix_sl_patient_instruction_task_patient_id'), table_name='sl_patient_instruction_task')
    op.drop_index(op.f('ix_sl_patient_instruction_task_plan_id'), table_name='sl_patient_instruction_task')
    op.drop_table('sl_patient_instruction_task')

    op.drop_index(op.f('ix_sl_patient_instruction_plan_status'), table_name='sl_patient_instruction_plan')
    op.drop_index(op.f('ix_sl_patient_instruction_plan_template_id'), table_name='sl_patient_instruction_plan')
    op.drop_index(op.f('ix_sl_patient_instruction_plan_patient_id'), table_name='sl_patient_instruction_plan')
    op.drop_table('sl_patient_instruction_plan')

    op.drop_index(op.f('ix_sl_instruction_template_health_focus_code'), table_name='sl_instruction_template_health_focus')
    op.drop_index(op.f('ix_sl_instruction_template_health_focus_template_id'), table_name='sl_instruction_template_health_focus')
    op.drop_table('sl_instruction_template_health_focus')

    op.drop_index(op.f('ix_sl_instruction_template_status'), table_name='sl_instruction_template')
    op.drop_index(op.f('ix_sl_instruction_template_organization_id'), table_name='sl_instruction_template')
    op.drop_table('sl_instruction_template')

    op.drop_index(op.f('ix_sl_activity_template_status'), table_name='sl_activity_template')
    op.drop_index(op.f('ix_sl_activity_template_category_code'), table_name='sl_activity_template')
    op.drop_index(op.f('ix_sl_activity_template_organization_id'), table_name='sl_activity_template')
    op.drop_table('sl_activity_template')

    op.drop_column('sl_patient', 'timezone')
