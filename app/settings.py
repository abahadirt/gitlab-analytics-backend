from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    STATIC_ROOT: str = str(BASE_DIR / 'staticfiles')
    MEDIA_ROOT: str = str(BASE_DIR / 'media')

    # URLs
    MEDIA_URL: str = "/media/"
    STATIC_URL: str = "/static/"

    # Dynamic domain (useful for deployment)
    DOMAIN: str = "http://127.0.0.1:8000"  # Default to localhost for development

    # Full URLs (will be constructed dynamically)
    FULL_MEDIA_URL: str = ""  # To be dynamically generated later
    FULL_STATIC_URL: str = ""  # To be dynamically generated later

    # Security
    SECRET_KEY: str = "django-insecure-...."
    DEBUG: bool = True

    # Cache (Redis)
    REDIS_URL: str = "redis://redis:6379/1"
    CACHE_TIMEOUT: int = 5 * 60 * 60

    # Session
    SESSION_COOKIE_SAMESITE: str = 'Lax'
    SESSION_COOKIE_SECURE: bool = False
    CSRF_COOKIE_SAMESITE: str = 'Lax'
    CSRF_COOKIE_SECURE: bool = False

    # Gitlab Settings
    GITLAB_CLIENT_ID: str = '...'
    GITLAB_CLIENT_SECRET: str = 'gloas-...'
    GITLAB_AUTHORIZE_URL: str = 'https://gitlab.com/oauth/authorize'
    GITLAB_TOKEN_URL: str = 'https://gitlab.com/oauth/token'
    GITLAB_REDIRECT_URI: str = 'http://127.0.0.1:8000/auth/callback/'
    GITLAB_DEFAULT_TOKEN: str = 'glpat....'

    # Internationalization
    LANGUAGE_CODE: str = 'en-us'
    TIME_ZONE: str = 'UTC'

    class Config:
        env_file = ".env"  # This tells pydantic to read from .env file
        env_file_encoding = "utf-8"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Dynamically create full media and static URLs
        self.FULL_MEDIA_URL = f"{self.DOMAIN}{self.MEDIA_URL}"
        self.FULL_STATIC_URL = f"{self.DOMAIN}{self.STATIC_URL}"


settings = Settings()
