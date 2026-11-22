from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, loaded from environment variables or .env."""

    app_name: str = "心愿罐"
    app_version: str = "dev"
    database_url: str = "sqlite:///./data/wishjar.db"
    secret_key: str = "dev-only-change-me-in-production"
    cookie_name: str = "wishjar_session"
    cookie_secure: bool = False
    session_max_age_days: int = 30
    timezone: str = "Asia/Shanghai"
    data_dir: str = "./data"
    upload_dir: str = "./data/uploads"
    backup_dir: str = "./data/backups"
    frontend_dist: str = ""
    auto_migrate: bool = True
    enable_scheduler: bool = True
    backup_keep: int = 14

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
