"""Add database indexes for performance optimization

Revision ID: add_performance_indexes
Revises: e9a759611ce2
Create Date: 2025-10-09 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_performance_indexes'
down_revision = 'e9a759611ce2'
branch_labels = None
depends_on = None


def upgrade():
    """Add composite indexes for better query performance."""
    
    # Index for bank_rates: frequently queried by (code, fetched_at) or (bank_id, code, fetched_at)
    op.create_index(
        'ix_bank_rates_code_fetched_at',
        'bank_rates',
        ['code', sa.text('fetched_at DESC')],
        unique=False
    )
    
    op.create_index(
        'ix_bank_rates_bank_code_fetched',
        'bank_rates',
        ['bank_id', 'code', sa.text('fetched_at DESC')],
        unique=False
    )
    
    # Index for cbu_rates: frequently queried by (code, rate_date)
    op.create_index(
        'ix_cbu_rates_code_date',
        'cbu_rates',
        ['code', sa.text('rate_date DESC')],
        unique=False
    )
    
    # Index for users: frequently filter by subscribed status
    op.create_index(
        'ix_users_subscribed',
        'users',
        ['subscribed'],
        unique=False
    )
    
    # Index for dashboards: frequently query active dashboards by user
    op.create_index(
        'ix_dashboards_user_active',
        'dashboards',
        ['user_id', 'is_active'],
        unique=False
    )


def downgrade():
    """Remove the indexes."""
    op.drop_index('ix_dashboards_user_active', table_name='dashboards')
    op.drop_index('ix_users_subscribed', table_name='users')
    op.drop_index('ix_cbu_rates_code_date', table_name='cbu_rates')
    op.drop_index('ix_bank_rates_bank_code_fetched', table_name='bank_rates')
    op.drop_index('ix_bank_rates_code_fetched_at', table_name='bank_rates')
