from pydantic_settings import BaseSettings
from cryptography.fernet import Fernet


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://trader:trader_secret@db:5432/trader_history"
    encryption_key: str = ""

    model_config = {"env_file": ".env"}

    def get_fernet(self) -> Fernet:
        key = self.encryption_key
        if not key:
            key = Fernet.generate_key().decode()
        return Fernet(key.encode() if isinstance(key, str) else key)


settings = Settings()
