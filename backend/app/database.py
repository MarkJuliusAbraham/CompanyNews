from collections.abc import Iterator

from sqlalchemy import URL, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

url = URL.create(
    "postgresql+psycopg",
    username=settings.postgres_user,
    password=settings.postgres_password,
    host=settings.postgres_host,
    port=settings.postgres_port,
    database=settings.postgres_db,
)

engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 3})
SessionLocal = sessionmaker(engine)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
