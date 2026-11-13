from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from asaa_ap.config import get_settings


class Base(DeclarativeBase):
    pass


def build_session_factory(database_url: str | None = None):
    url = database_url or get_settings().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    options = {"pool_pre_ping": True, "connect_args": connect_args}
    if url.startswith(("postgresql://", "postgresql+psycopg://")):
        settings = get_settings()
        options.update({
            "pool_size": settings.db_pool_size,
            "max_overflow": settings.db_max_overflow,
            "pool_timeout": settings.db_pool_timeout_seconds,
            "pool_recycle": settings.db_pool_recycle_seconds,
            "connect_args": {
                "connect_timeout": settings.db_connect_timeout_seconds,
                "application_name": "asaa-enterprise-api",
            },
        })
    engine = create_engine(url, **options)
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


engine, SessionLocal = build_session_factory()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
