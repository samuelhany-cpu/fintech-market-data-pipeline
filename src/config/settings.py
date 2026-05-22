import os

from pydantic_settings import BaseSettings


def _get_database_url() -> str:
    """Read DATABASE_URL from env, .env file, or Streamlit secrets (cloud)."""
    # Env var / .env file takes priority
    url = os.environ.get("DATABASE_URL", "")
    if url:
        return url
    # Streamlit Cloud injects secrets as env vars automatically,
    # but also supports st.secrets — try that as a fallback.
    try:
        import streamlit as st  # noqa: PLC0415
        return st.secrets.get("DATABASE_URL", "")
    except Exception:
        return ""


class Settings(BaseSettings):
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "market_data"
    postgres_user: str = "market_user"
    postgres_password: str = "market_password"

    database_url: str = ""
    log_level: str = "INFO"

    @property
    def db_url(self) -> str:
        url = self.database_url or _get_database_url()
        if url:
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg://", 1)
            if "supabase.co" in url and "sslmode" not in url:
                url += "?sslmode=require"
            return url
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
