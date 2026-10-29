from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = depends_on = None


def upgrade():
    # Older sessions have no known opening date; do not invent new consultations.
    op.add_column('learning_sessions', sa.Column('created_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('feedback', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()))
    op.create_table('ingestion_records', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('user_id', sa.String(), sa.ForeignKey('users.id'), nullable=False), sa.Column('received_at', sa.DateTime(timezone=True), nullable=False), sa.Column('accepted', sa.Integer(), nullable=False), sa.Column('duplicate', sa.Integer(), nullable=False), sa.Column('rejected', sa.Integer(), nullable=False))
    op.create_index('ix_ingestion_records_user_id', 'ingestion_records', ['user_id'])
    op.create_index('ix_ingestion_records_received_at', 'ingestion_records', ['received_at'])
    op.create_table('data_policy', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('retention_days', sa.Integer(), nullable=False), sa.Column('enabled', sa.Boolean(), nullable=False), sa.Column('pseudonym_key', sa.String(), nullable=False))


def downgrade():
    raise RuntimeError('Downgrade destructif non pris en charge')
