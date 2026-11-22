import sqlite3
from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from .config import Settings


def sqlite_database_path(settings: Settings) -> Path | None:
    url = make_url(settings.database_url)
    if url.get_backend_name() != "sqlite" or not url.database:
        return None
    if url.database == ":memory:":
        return None
    return Path(url.database).expanduser()


def prune_backups(settings: Settings) -> None:
    backup_dir = Path(settings.backup_dir)
    if not backup_dir.exists():
        return
    backups = sorted(backup_dir.glob("wishjar-*.db"), reverse=True)
    for old in backups[max(1, settings.backup_keep) :]:
        try:
            old.unlink()
        except OSError:
            pass


def backup_database(settings: Settings) -> Path | None:
    source_path = sqlite_database_path(settings)
    if source_path is None or not source_path.exists():
        return None
    backup_dir = Path(settings.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"wishjar-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
    with sqlite3.connect(source_path) as source, sqlite3.connect(target) as dest:
        source.backup(dest)
    prune_backups(settings)
    return target
