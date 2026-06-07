"""enable_pgvector_extension

Revision ID: 53949cafc750
Revises: bbb5942728eb
Create Date: 2026-06-06 15:54:54.599353

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '53949cafc750'
down_revision: Union[str, None] = 'bbb5942728eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This magically turns on the vector brain in Neon
    op.execute('CREATE EXTENSION IF NOT EXISTS vector;')

def downgrade() -> None:
    # This turns it off if we ever undo the migration
    op.execute('DROP EXTENSION IF EXISTS vector;')
