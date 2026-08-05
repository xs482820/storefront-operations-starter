from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "Storefront Operations API"
    APP_ENV: str = "production"
    APP_DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: str = "http://localhost:19080,http://127.0.0.1:19080"
    CORS_ALLOW_CREDENTIALS: bool = False
    PUBLIC_ASSET_BASE_URL: str = "http://localhost:19000"

    JWT_SECRET_KEY: str = Field(default="change-this-secret", min_length=16)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24
    EMPLOYEE_JWT_EXPIRE_MINUTES: int = 60 * 24 * 30

    DATABASE_URL: str = "postgresql+asyncpg://yyy:yyy_password@postgres:5432/yyy_hub"
    REDIS_URL: str = "redis://redis:6379/0"
    AUTH_SMS_MOCK: bool = False
    AUTH_SMS_CODE_TTL_SECONDS: int = 300
    AUTH_SMS_RESEND_SECONDS: int = 60

    WECHAT_PAY_MOCK: bool = True
    WECHAT_MCH_ID: str | None = None
    WECHAT_APP_ID: str | None = None
    WECHAT_MINI_APP_ID: str | None = None
    WECHAT_MINI_APP_SECRET: str | None = None
    WECHAT_EMPLOYEE_MINI_APP_ID: str | None = None
    WECHAT_EMPLOYEE_MINI_APP_SECRET: str | None = None
    WECHAT_NOTIFICATION_CHANNELS: str = "internal,miniapp_subscribe"
    WECHAT_API_V3_KEY: str | None = None
    WECHAT_SERIAL_NO: str | None = None
    WECHAT_PRIVATE_KEY_PATH: str | None = None
    WECHAT_PLATFORM_CERT_PATH: str | None = None
    WECHAT_PAY_PUBLIC_KEY_PATH: str | None = None
    WECHAT_PAY_PUBLIC_KEY_ID: str | None = None
    WECHAT_NOTIFY_URL: str | None = None
    WECHAT_REFUND_NOTIFY_URL: str | None = None

    SHIPPING_RETAIL_FREE_THRESHOLD: str = "99.00"
    SHIPPING_RETAIL_BASE_FEE: str = "8.00"
    ORDER_AUTO_CANCEL_MINUTES: int = 10

    SCHEDULER_ENABLED: bool = True
    SCHEDULER_INTERVAL_SECONDS: int = 300
    SCHEDULER_EXPRESS_AUTO_COMPLETE_DAYS: int = 3
    SCHEDULER_OFFLINE_AUTO_COMPLETE_DAYS: int = 10

    PRINT_PROVIDER: str = "reserved"
    PRINT_JOB_TTL_SECONDS: int = 604800
    PRINT_GATEWAY_TOKEN: str | None = None

    AI_ADMIN_ENABLED: bool = False
    AI_ADMIN_DRY_RUN: bool = True
    DEEPSEEK_API_KEY: str | None = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_TIMEOUT_SECONDS: int = 30
    DEEPSEEK_MAX_OUTPUT_TOKENS: int = 1200


@lru_cache
def get_settings() -> Settings:
    return Settings()
