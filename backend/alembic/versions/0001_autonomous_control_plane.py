"""Create the autonomous ArmorIQ control-plane schema."""

from alembic import op

try:
    from backend.app.db import Base
    from backend.app import models  # noqa: F401
except ModuleNotFoundError:
    from app.db import Base
    from app import models  # type: ignore[no-redef]  # noqa: F401

revision = "0001_autonomy"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
