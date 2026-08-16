"""sprint 1b speech audio artifacts and job durability

Revision ID: b21f9a1c3d4e
Revises: 166ad9ecb96e
Create Date: 2026-08-16
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Text
from sqlalchemy.dialects import postgresql

revision = "b21f9a1c3d4e"
down_revision = "166ad9ecb96e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("asr_normalizations") as batch_op:
        batch_op.alter_column("vocabulary_version_id", existing_type=sa.Uuid(), nullable=True)
        batch_op.add_column(
            sa.Column(
                "normalizer_ruleset_version",
                sa.String(length=32),
                nullable=False,
                server_default="builtin-v1",
            )
        )
    op.create_table(
        "media_assets",
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("codec", sa.String(length=32), nullable=True),
        sa.Column("sample_rate", sa.Integer(), nullable=True),
        sa.Column("channels", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "retention",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("attempt_id", sa.Uuid(), nullable=True),
        sa.Column("attempt_item_id", sa.Uuid(), nullable=True),
        sa.Column("answer_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["answer_id"], ["answers.id"]),
        sa.ForeignKeyConstraint(["attempt_id"], ["exam_attempts.id"]),
        sa.ForeignKeyConstraint(["attempt_item_id"], ["attempt_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_media_asset_storage_key"),
    )
    with op.batch_alter_table("answers") as batch_op:
        batch_op.add_column(sa.Column("audio_asset_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_answers_audio_asset_id", "media_assets", ["audio_asset_id"], ["id"]
        )
    op.add_column("ai_calls", sa.Column("latency_ms", sa.Integer(), nullable=True))

    with op.batch_alter_table("task_jobs") as batch_op:
        batch_op.add_column(sa.Column("attempt_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("attempt_item_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("answer_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("ai_call_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("run_after", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_foreign_key(
            "fk_task_jobs_attempt_id", "exam_attempts", ["attempt_id"], ["id"]
        )
        batch_op.create_foreign_key(
            "fk_task_jobs_attempt_item_id", "attempt_items", ["attempt_item_id"], ["id"]
        )
        batch_op.create_foreign_key("fk_task_jobs_answer_id", "answers", ["answer_id"], ["id"])
        batch_op.create_foreign_key("fk_task_jobs_ai_call_id", "ai_calls", ["ai_call_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("asr_normalizations") as batch_op:
        batch_op.drop_column("normalizer_ruleset_version")
        batch_op.alter_column("vocabulary_version_id", existing_type=sa.Uuid(), nullable=False)
    with op.batch_alter_table("task_jobs") as batch_op:
        batch_op.drop_constraint("fk_task_jobs_ai_call_id", type_="foreignkey")
        batch_op.drop_constraint("fk_task_jobs_answer_id", type_="foreignkey")
        batch_op.drop_constraint("fk_task_jobs_attempt_item_id", type_="foreignkey")
        batch_op.drop_constraint("fk_task_jobs_attempt_id", type_="foreignkey")
        batch_op.drop_column("completed_at")
        batch_op.drop_column("run_after")
        batch_op.drop_column("ai_call_id")
        batch_op.drop_column("answer_id")
        batch_op.drop_column("attempt_item_id")
        batch_op.drop_column("attempt_id")
    op.drop_column("ai_calls", "latency_ms")
    with op.batch_alter_table("answers") as batch_op:
        batch_op.drop_constraint("fk_answers_audio_asset_id", type_="foreignkey")
        batch_op.drop_column("audio_asset_id")
    op.drop_table("media_assets")
