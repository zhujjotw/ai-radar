from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from src.config import resolve_db_path


def get_database_url(db_path: Path | None = None) -> str:
    path = db_path or resolve_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


engine = create_engine(get_database_url(), connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)

