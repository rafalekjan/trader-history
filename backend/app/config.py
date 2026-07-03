from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://trader:trader_secret@db:5432/trader_history"

    model_config = {"env_file": ".env"}


settings = Settings()
