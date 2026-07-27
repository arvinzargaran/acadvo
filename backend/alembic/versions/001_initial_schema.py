"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enums
    message_role = sa.Enum("user", "assistant", name="message_role")
    course_status = sa.Enum("completed", "in_progress", "planned", "not_scheduled", name="course_status")
    project_status = sa.Enum("not_started", "in_progress", "deployed", "interview_ready", name="project_status")
    milestone_status = sa.Enum("pending", "in_progress", "complete", "overdue", name="milestone_status")
    career_status = sa.Enum("researching", "applied", "interviewing", "offer", "rejected", name="career_status")
    timeline_category = sa.Enum("deadline", "milestone", "goal", "co_op", "academic", name="timeline_category")
    suggestion_type = sa.Enum("course", "project", "career", "schedule", "risk_flag", name="suggestion_type")
    risk_severity = sa.Enum("low", "medium", "high", name="risk_severity")

    # users
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("university", sa.Text),
        sa.Column("program", sa.Text),
        sa.Column("start_year", sa.Integer),
        sa.Column("expected_graduation_year", sa.Integer),
        sa.Column("country", sa.String(100)),
        sa.Column("city", sa.String(100)),
        sa.Column("career_target", sa.Text),
        sa.Column("onboarding_complete", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # refresh_tokens
    op.create_table(
        "refresh_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(500), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token", "refresh_tokens", ["token"], unique=True)

    # conversations
    op.create_table(
        "conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255)),
        sa.Column("is_onboarding", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("context_snapshot", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])

    # messages
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", message_role, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("tool_calls", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_created_at", "messages", ["created_at"])

    # degree_requirements
    op.create_table(
        "degree_requirements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bucket_name", sa.Text, nullable=False),
        sa.Column("credits_required", sa.Numeric(5, 2), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_degree_requirements_user_id", "degree_requirements", ["user_id"])

    # credentials
    op.create_table(
        "credentials",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("total_credits_required", sa.Numeric(5, 2)),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_credentials_user_id", "credentials", ["user_id"])

    # courses
    op.create_table(
        "courses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_code", sa.String(20), nullable=False),
        sa.Column("course_name", sa.String(255), nullable=False),
        sa.Column("credit_value", sa.Numeric(4, 2), nullable=False),
        sa.Column("status", course_status, nullable=False, server_default="not_scheduled"),
        sa.Column("term", sa.String(50)),
        sa.Column("grade", sa.String(10)),
        sa.Column("requirement_bucket_id", UUID(as_uuid=True), sa.ForeignKey("degree_requirements.id", ondelete="SET NULL")),
        sa.Column("credential_id", UUID(as_uuid=True), sa.ForeignKey("credentials.id", ondelete="SET NULL")),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_courses_user_id", "courses", ["user_id"])
    op.create_index("ix_courses_status", "courses", ["status"])
    op.create_index("ix_courses_requirement_bucket_id", "courses", ["requirement_bucket_id"])

    # projects
    op.create_table(
        "projects",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("priority", sa.Integer, nullable=False),
        sa.Column("status", project_status, nullable=False, server_default="not_started"),
        sa.Column("tech_stack", sa.Text),
        sa.Column("repo_url", sa.Text),
        sa.Column("live_url", sa.Text),
        sa.Column("demo_url", sa.Text),
        sa.Column("hard_deadline", sa.Date),
        sa.Column("product_framing", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("priority >= 1 AND priority <= 3", name="ck_projects_priority"),
    )
    op.create_index("ix_projects_user_id", "projects", ["user_id"])
    op.create_index("ix_projects_status", "projects", ["status"])

    # milestones
    op.create_table(
        "milestones",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("target_date", sa.Date),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("status", milestone_status, nullable=False, server_default="pending"),
        sa.Column("order_index", sa.Integer, nullable=False, server_default=sa.text("0")),
    )
    op.create_index("ix_milestones_project_id", "milestones", ["project_id"])

    # career_targets
    op.create_table(
        "career_targets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("role_type", sa.String(255)),
        sa.Column("location", sa.String(255)),
        sa.Column("status", career_status, nullable=False, server_default="researching"),
        sa.Column("target_term", sa.String(50)),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_career_targets_user_id", "career_targets", ["user_id"])

    # timeline_events
    op.create_table(
        "timeline_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("event_date", sa.Date, nullable=False),
        sa.Column("category", timeline_category, nullable=False),
        sa.Column("is_hard_deadline", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_timeline_events_user_id", "timeline_events", ["user_id"])
    op.create_index("ix_timeline_events_event_date", "timeline_events", ["event_date"])

    # ai_suggestions
    op.create_table(
        "ai_suggestions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="SET NULL")),
        sa.Column("suggestion_type", suggestion_type, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("severity", risk_severity),
        sa.Column("accepted", sa.Boolean),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ai_suggestions_user_id", "ai_suggestions", ["user_id"])


def downgrade() -> None:
    op.drop_table("ai_suggestions")
    op.drop_table("timeline_events")
    op.drop_table("career_targets")
    op.drop_table("milestones")
    op.drop_table("projects")
    op.drop_table("courses")
    op.drop_table("credentials")
    op.drop_table("degree_requirements")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("refresh_tokens")
    op.drop_table("users")

    for enum_name in [
        "risk_severity", "suggestion_type", "timeline_category",
        "career_status", "milestone_status", "project_status",
        "course_status", "message_role",
    ]:
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
