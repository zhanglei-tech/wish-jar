from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import Settings


class Base(DeclarativeBase):
    pass


def _is_sqlite(url: str) -> bool:
    return make_url(url).get_backend_name() == "sqlite"


def create_engine_for(settings: Settings):
    url = settings.database_url
    if _is_sqlite(url):
        database = make_url(url).database
        if database and database != ":memory:":
            Path(database).expanduser().parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        url,
        future=True,
        connect_args={"check_same_thread": False, "timeout": 30}
        if _is_sqlite(url)
        else {},
    )

    if _is_sqlite(url):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

    return engine


def create_session_factory(engine) -> sessionmaker[Session]:
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
