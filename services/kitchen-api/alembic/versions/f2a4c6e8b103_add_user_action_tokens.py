"""add user action tokens

Revision ID: f2a4c6e8b103
Revises: a19c7e4d2b60
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f2a4c6e8b103"
down_revision: str | Sequence[str] | None = "a19c7e4d2b60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM users
                    WHERE email <> lower(btrim(email))
                ) THEN
                    RAISE EXCEPTION
                        'users contains non-normalized email values';
                END IF;
                IF EXISTS (
                    SELECT lower(btrim(email))
                    FROM users
                    GROUP BY lower(btrim(email))
                    HAVING count(*) > 1
                ) THEN
                    RAISE EXCEPTION
                        'users contains conflicting normalized email values';
                END IF;
            END
            $$;
            """
        )
    )
    op.create_check_constraint(
        "ck_user_email_normalized",
        "users",
        "email = lower(btrim(email))",
    )
    op.create_table(
        "user_action_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "purpose IN ('email_verification', 'password_reset')",
            name="ck_user_action_token_purpose",
        ),
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_user_action_token_expiry",
        ),
        sa.CheckConstraint(
            "used_at IS NULL OR used_at >= created_at",
            name="ck_user_action_token_used_at",
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name="ck_user_action_token_revoked_at",
        ),
        sa.CheckConstraint(
            "NOT (used_at IS NOT NULL AND revoked_at IS NOT NULL)",
            name="ck_user_action_token_terminal_state",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_user_action_token_hash"),
    )
    op.create_index(
        "ix_user_action_token_history",
        "user_action_tokens",
        ["user_id", "purpose", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_action_token_history",
        table_name="user_action_tokens",
    )
    op.drop_table("user_action_tokens")
    op.drop_constraint("ck_user_email_normalized", "users", type_="check")
