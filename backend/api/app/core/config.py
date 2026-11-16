from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    sentinelops_database_url: str | None = None
    sentinelops_jwt_secret: SecretStr | None = None
    sentinelops_operator: str = "operator"
    sentinelops_password_hash: SecretStr | None = None
    dashboard_origins: str = "http://localhost:5173"


settings = Settings()
