"""make mpesa user_id nullable for guest transactions

Revision ID: a1b2c3d4e5f6
Revises: 9156570cfff3
Create Date: 2026-02-07 09:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '9156570cfff3'
branch_labels = None
depends_on = None


def upgrade():
    # Make user_id nullable for guest transactions
    with op.batch_alter_table('mpesa_transactions', schema=None) as batch_op:
        batch_op.alter_column('user_id',
               existing_type=sa.INTEGER(),
               nullable=True)


def downgrade():
    # Revert user_id to NOT NULL
    with op.batch_alter_table('mpesa_transactions', schema=None) as batch_op:
        batch_op.alter_column('user_id',
               existing_type=sa.INTEGER(),
               nullable=False)
