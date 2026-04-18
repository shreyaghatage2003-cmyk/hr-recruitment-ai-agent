from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    openai_api_key: str = ""
    sendgrid_api_key: str = ""
    sendgrid_from_email: str = "hr@company.com"
    google_calendar_credentials_json: Optional[str] = None
    database_url: str = "sqlite+aiosqlite:///./hr_recruitment.db"
    secret_key: str = "changeme"
    hr_email: str = "hr@company.com"
    frontend_url: str = "http://localhost:8000"

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key and self.openai_api_key not in ("your_openai_api_key_here", ""))

    @property
    def has_sendgrid(self) -> bool:
        return bool(self.sendgrid_api_key and self.sendgrid_api_key not in ("your_sendgrid_api_key_here", ""))

    class Config:
        env_file = ".env"


settings = Settings()
