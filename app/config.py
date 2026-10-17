from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    database_url: str = "sqlite:///./data/flexi.db"
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
