"""add all missing models

Revision ID: 5e6cbf2519f4
Revises: 21da97ac1cf8
Create Date: 2026-02-06 10:52:53.234675

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '5e6cbf2519f4'
down_revision = '21da97ac1cf8'
branch_labels = None
depends_on = None


def upgrade():
    # Clear all affected tables to avoid NOT NULL violations
    op.execute("TRUNCATE TABLE mpesa_transactions CASCADE")
    op.execute("TRUNCATE TABLE tickets CASCADE")
    op.execute("TRUNCATE TABLE ticket_types CASCADE")
    op.execute("TRUNCATE TABLE events CASCADE")
    
    # Create categories table
    op.create_table('categories',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=50), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('icon', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    
    # Add new columns to event_reviews
    with op.batch_alter_table('event_reviews', schema=None) as batch_op:
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))

    # Update events table - add new columns first
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('venue', sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column('address', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('category_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('has_tickets', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('max_attendees', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('early_bird_end_date', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('is_published', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('is_featured', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('view_count', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('moderated_by', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('moderated_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('moderation_notes', sa.Text(), nullable=True))
    
    # Add foreign keys after columns are added
    op.execute("ALTER TABLE events ADD CONSTRAINT fk_events_category FOREIGN KEY (category_id) REFERENCES categories(id)")
    op.execute("ALTER TABLE events ADD CONSTRAINT fk_events_moderated_by FOREIGN KEY (moderated_by) REFERENCES users(id)")
    
    # Drop old columns from events
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.drop_column('venue_address')
        batch_op.drop_column('location')
        batch_op.drop_column('category')

    # Update mpesa_transactions - add new columns first (nullable)
    with op.batch_alter_table('mpesa_transactions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))  # Nullable for guest transactions
        batch_op.add_column(sa.Column('event_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('ticket_type_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('quantity', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('checkout_request_id', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('mpesa_receipt', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('reference', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('completed_at', sa.DateTime(), nullable=True))
    
    # Now alter to NOT NULL and drop old columns
    with op.batch_alter_table('mpesa_transactions', schema=None) as batch_op:
        batch_op.alter_column('amount',
               existing_type=sa.NUMERIC(precision=10, scale=2),
               nullable=False)
        batch_op.alter_column('transaction_id',
               existing_type=sa.VARCHAR(length=100),
               nullable=True)
        batch_op.drop_constraint(batch_op.f('mpesa_transactions_transaction_id_key'), type_='unique')
        batch_op.drop_constraint(batch_op.f('mpesa_transactions_ticket_id_fkey'), type_='foreignkey')
    
    # Add foreign keys
    op.execute("ALTER TABLE mpesa_transactions ADD CONSTRAINT fk_mpesa_user FOREIGN KEY (user_id) REFERENCES users(id)")
    op.execute("ALTER TABLE mpesa_transactions ADD CONSTRAINT fk_mpesa_event FOREIGN KEY (event_id) REFERENCES events(id)")
    op.execute("ALTER TABLE mpesa_transactions ADD CONSTRAINT fk_mpesa_ticket_type FOREIGN KEY (ticket_type_id) REFERENCES ticket_types(id)")
    
    # Drop old columns from mpesa_transactions
    with op.batch_alter_table('mpesa_transactions', schema=None) as batch_op:
        batch_op.drop_column('middle_name')
        batch_op.drop_column('bill_reference')
        batch_op.drop_column('transaction_time')
        batch_op.drop_column('org_account_balance')
        batch_op.drop_column('result_code')
        batch_op.drop_column('short_code')
        batch_op.drop_column('first_name')
        batch_op.drop_column('last_name')
        batch_op.drop_column('transaction_type')
        batch_op.drop_column('ticket_id')

    # Update ticket_types
    with op.batch_alter_table('ticket_types', schema=None) as batch_op:
        batch_op.add_column(sa.Column('quantity_new', sa.Integer(), nullable=False))
    
    # Copy data from old column to new column
    op.execute("UPDATE ticket_types SET quantity_new = COALESCE(quantity_total, 0)")
    
    with op.batch_alter_table('ticket_types', schema=None) as batch_op:
        batch_op.drop_column('quantity_total')
        batch_op.drop_column('quantity_sold')
        batch_op.add_column(sa.Column('sold_quantity', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('benefits', sa.Text(), nullable=True))
        batch_op.drop_column('quantity_new')


def downgrade():
    # First add back the old columns
    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('verified_by', sa.INTEGER(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('mpesa_receipt', sa.VARCHAR(length=100), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('payment_status', postgresql.ENUM('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'REFUNDED', name='paymentstatus'), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('quantity', sa.INTEGER(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('total_price', sa.NUMERIC(precision=10, scale=2), autoincrement=False, nullable=False))
        batch_op.add_column(sa.Column('ticket_number', sa.VARCHAR(length=20), autoincrement=False, nullable=False))
        batch_op.add_column(sa.Column('is_used', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True))
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.create_foreign_key(batch_op.f('tickets_verified_by_fkey'), 'users', ['verified_by'], ['id'])
        batch_op.drop_constraint(None, type_='unique')
        batch_op.create_unique_constraint(batch_op.f('tickets_ticket_number_key'), ['ticket_number'])
        batch_op.drop_column('used_by')
        batch_op.drop_column('qr_data')
        batch_op.drop_column('qr_code')
        batch_op.drop_column('status')
        batch_op.drop_column('ticket_code')

    with op.batch_alter_table('ticket_types', schema=None) as batch_op:
        batch_op.add_column(sa.Column('quantity_total', sa.INTEGER(), autoincrement=False, nullable=False))
        batch_op.add_column(sa.Column('quantity_sold', sa.INTEGER(), autoincrement=False, nullable=True))
        batch_op.drop_column('benefits')
        batch_op.drop_column('sold_quantity')
        batch_op.drop_column('quantity')

    with op.batch_alter_table('mpesa_transactions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ticket_id', sa.INTEGER(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('transaction_type', sa.VARCHAR(length=50), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('last_name', sa.VARCHAR(length=100), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('first_name', sa.VARCHAR(length=100), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('short_code', sa.VARCHAR(length=20), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('result_code', sa.INTEGER(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('org_account_balance', sa.VARCHAR(length=100), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('transaction_time', postgresql.TIMESTAMP(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('bill_reference', sa.VARCHAR(length=100), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('middle_name', sa.VARCHAR(length=100), autoincrement=False, nullable=True))
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.create_foreign_key(batch_op.f('mpesa_transactions_ticket_id_fkey'), 'tickets', ['ticket_id'], ['id'])
        batch_op.create_unique_constraint(batch_op.f('mpesa_transactions_transaction_id_key'), ['transaction_id'])
        batch_op.alter_column('transaction_id',
               existing_type=sa.VARCHAR(length=100),
               nullable=False)
        batch_op.alter_column('amount',
               existing_type=sa.NUMERIC(precision=10, scale=2),
               nullable=True)
        batch_op.drop_column('completed_at')
        batch_op.drop_column('reference')
        batch_op.drop_column('mpesa_receipt')
        batch_op.drop_column('checkout_request_id')
        batch_op.drop_column('quantity')
        batch_op.drop_column('ticket_type_id')
        batch_op.drop_column('event_id')
        batch_op.drop_column('user_id')

    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('category', sa.VARCHAR(length=50), autoincrement=False, nullable=False))
        batch_op.add_column(sa.Column('location', sa.VARCHAR(length=300), autoincrement=False, nullable=False))
        batch_op.add_column(sa.Column('venue_address', sa.VARCHAR(length=500), autoincrement=False, nullable=True))
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('moderation_notes')
        batch_op.drop_column('moderated_at')
        batch_op.drop_column('moderated_by')
        batch_op.drop_column('view_count')
        batch_op.drop_column('is_featured')
        batch_op.drop_column('is_published')
        batch_op.drop_column('early_bird_end_date')
        batch_op.drop_column('max_attendees')
        batch_op.drop_column('has_tickets')
        batch_op.drop_column('category_id')
        batch_op.drop_column('address')
        batch_op.drop_column('venue')

    with op.batch_alter_table('event_reviews', schema=None) as batch_op:
        batch_op.drop_column('updated_at')

    op.drop_table('categories')
