"""Initial database migration

Revision ID: initial
Revises:
Create Date: 2026-02-08

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("role", sa.String(20), default="attendee"),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("is_verified", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("phone"),
    )

    # Create categories table
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # Create events table
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("venue", sa.String(255), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("start_date", sa.DateTime, nullable=False),
        sa.Column("end_date", sa.DateTime, nullable=False),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("category_id", sa.Integer, nullable=True),
        sa.Column("organizer_id", sa.Integer, nullable=True),
        sa.Column("banner_image", sa.String(500), nullable=True),
        sa.Column("total_capacity", sa.Integer, default=100),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["organizer_id"], ["users.id"]),
    )

    # Create ticket_types table
    op.create_table(
        "ticket_types",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("price", sa.Float, nullable=False),
        sa.Column("quantity_available", sa.Integer, nullable=False),
        sa.Column("quantity_sold", sa.Integer, default=0),
        sa.Column("sales_start", sa.DateTime, nullable=True),
        sa.Column("sales_end", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
    )

    # Create tickets table
    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticket_number", sa.String(50), nullable=False),
        sa.Column("event_id", sa.Integer, nullable=False),
        sa.Column("user_id", sa.Integer, nullable=True),
        sa.Column("guest_email", sa.String(255), nullable=True),
        sa.Column("guest_phone", sa.String(20), nullable=True),
        sa.Column("ticket_type_id", sa.Integer, nullable=False),
        sa.Column("quantity", sa.Integer, default=1),
        sa.Column("total_price", sa.Float, nullable=False),
        sa.Column("payment_status", sa.String(20), default="pending"),
        sa.Column("qr_code", sa.String(500), nullable=True),
        sa.Column("used_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["ticket_type_id"], ["ticket_types.id"]),
        sa.UniqueConstraint("ticket_number"),
    )

    # Create mpesa_transactions table
    op.create_table(
        "mpesa_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer, nullable=True),
        sa.Column("event_id", sa.Integer, nullable=True),
        sa.Column("ticket_id", sa.Integer, nullable=True),
        sa.Column("amount", sa.Float, nullable=False),
        sa.Column("phone_number", sa.String(20), nullable=False),
        sa.Column("transaction_id", sa.String(100), nullable=True),
        sa.Column("mpesa_receipt", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("result_desc", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
    )

    # Create reviews table
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer, nullable=False),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("rating", sa.Integer, nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )

    # Create saved_events table
    op.create_table(
        "saved_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("event_id", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.UniqueConstraint("user_id", "event_id", name="_user_event_uc"),
    )

    # Create event_images table
    op.create_table(
        "event_images",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer, nullable=False),
        sa.Column("image_url", sa.String(500), nullable=False),
        sa.Column("image_type", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
    )


def downgrade():
    op.drop_table("event_images")
    op.drop_table("saved_events")
    op.drop_table("reviews")
    op.drop_table("mpesa_transactions")
    op.drop_table("tickets")
    op.drop_table("ticket_types")
    op.drop_table("events")
    op.drop_table("categories")
    op.drop_table("users")
