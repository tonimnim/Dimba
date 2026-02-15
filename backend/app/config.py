import os
from datetime import timedelta


def _fix_db_url(url):
    """Ensure postgresql:// URLs use the psycopg3 driver."""
    if url and url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
    }

    # CORS
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")

    # Rate limiting
    RATELIMIT_STORAGE_URI = "memory://"


class DevelopmentConfig(Config):
    DEBUG = True
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-dev-secret")
    SQLALCHEMY_DATABASE_URI = _fix_db_url(
        os.getenv("DATABASE_URL", "postgresql://premia:premia@localhost:5432/premia")
    )


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret-key"
    JWT_SECRET_KEY = "test-jwt-secret"
    SQLALCHEMY_DATABASE_URI = _fix_db_url(
        os.getenv("DATABASE_URL", "postgresql://premia:premia@localhost:5432/premia_test")
    )
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    RATELIMIT_ENABLED = False


class ProductionConfig(Config):
    DEBUG = False
    SECRET_KEY = os.getenv("SECRET_KEY")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = _fix_db_url(
        os.getenv("DATABASE_URL", "postgresql://premia:premia@db:5432/premia")
    )

    @staticmethod
    def init_app(app):
        for key in ("SECRET_KEY", "JWT_SECRET_KEY"):
            if not app.config.get(key):
                raise RuntimeError(f"{key} must be set in production")


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
