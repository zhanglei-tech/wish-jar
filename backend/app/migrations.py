from pathlib import Path

from alembic import command
from alembic.config import Config

from .config import Settings


def run_migrations(settings: Settings) -> None:
    backend_dir = Path(__file__).resolve().parent.parent
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    config.set_main_option(
        "sqlalchemy.url", settings.database_url.replace("%", "%%")
    )
    command.upgrade(config, "head")
