from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Iterator

from sqlmodel import Session, SQLModel, create_engine

from .core.config import get_settings

settings = get_settings()


def _build_engine():
    db_url = settings.database_url
    if db_url.startswith("sqlite"):
        db_path = db_url.split("///")[-1]
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        return create_engine(db_url, connect_args={"check_same_thread": False})
    return create_engine(db_url)


engine = _build_engine()


def init_db() -> None:
    SQLModel.metadata.create_all(bind=engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
