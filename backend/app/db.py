from collections.abc import Generator
from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from app.config import resolve_db_path


def get_database_url(db_path: Path | None = None) -> str:
    path = db_path or resolve_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


engine = create_engine(get_database_url(), connect_args={"check_same_thread": False})


def _migrate_new_columns() -> None:
    """Add columns that may not exist in older SQLite databases."""
    new_columns = [
        ("projects", "llm_description", "TEXT"),
        ("projects", "llm_scenarios", "TEXT"),
    ]
    with engine.connect() as conn:
        for table, column, col_type in new_columns:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
                conn.commit()
            except Exception:
                pass  # Column already exists


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _migrate_new_columns()


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    with Session(engine) as session:
        yield session
