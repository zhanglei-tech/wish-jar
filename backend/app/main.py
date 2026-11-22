import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .backup import backup_database, sqlite_database_path
from .config import Settings
from .db import create_engine_for, create_session_factory
from .migrations import run_migrations
from .routes import router


def _frontend_dist(settings: Settings) -> Path:
    if settings.frontend_dist:
        return Path(settings.frontend_dist)
    return Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    for directory in (
        settings.data_dir,
        settings.upload_dir,
        settings.backup_dir,
    ):
        Path(directory).mkdir(parents=True, exist_ok=True)

    if settings.auto_migrate:
        database_path = sqlite_database_path(settings)
        existing_backup = (
            backup_database(settings)
            if database_path is not None and database_path.exists()
            else None
        )
        try:
            run_migrations(settings)
        except Exception:
            if existing_backup is not None and database_path is not None:
                app.state.engine.dispose()
                shutil.copy2(existing_backup, database_path)
            raise

    scheduler = None
    if settings.enable_scheduler:
        scheduler = BackgroundScheduler(timezone=settings.timezone)
        scheduler.add_job(
            lambda: backup_database(settings),
            "cron",
            hour=3,
            minute=10,
            id="daily-backup",
            replace_existing=True,
        )
        scheduler.start()
        app.state.scheduler = scheduler

    yield

    if scheduler is not None:
        scheduler.shutdown(wait=False)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = create_engine_for(settings)
    app.state.session_factory = create_session_factory(app.state.engine)
    app.include_router(router)

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/uploads",
        StaticFiles(directory=str(upload_dir)),
        name="uploads",
    )

    dist = _frontend_dist(settings)
    index_file = dist / "index.html"
    if index_file.is_file():
        assets = dist / "assets"
        if assets.is_dir():
            app.mount(
                "/assets",
                StaticFiles(directory=str(assets)),
                name="assets",
            )

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            if full_path.startswith(("api/", "uploads/")):
                raise HTTPException(status_code=404, detail="Not found")
            target = (dist / full_path).resolve()
            try:
                target.relative_to(dist.resolve())
            except ValueError:
                raise HTTPException(status_code=404, detail="Not found")
            if target.is_file():
                return FileResponse(target)
            return FileResponse(index_file)

    return app


app = create_app()
