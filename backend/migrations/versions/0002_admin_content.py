from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = depends_on = None


def upgrade():
    op.add_column('users', sa.Column('role', sa.String(), nullable=False, server_default='learner'))
    op.create_table('courses', sa.Column('id', sa.String(), primary_key=True), sa.Column('title', sa.String(), nullable=False), sa.Column('description', sa.String(), nullable=False), sa.Column('archived', sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table('resources') as batch:
        batch.add_column(sa.Column('course_id', sa.String(), nullable=True))
        batch.add_column(sa.Column('object_key', sa.String(), nullable=True))
        batch.add_column(sa.Column('archived', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.create_foreign_key('fk_resources_course', 'courses', ['course_id'], ['id'])


def downgrade():
    raise RuntimeError('Downgrade destructif non pris en charge')
