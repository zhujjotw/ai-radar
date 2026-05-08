from src.db import init_db, resolve_db_path


def main() -> None:
    init_db()
    print(f"Initialized database at {resolve_db_path()}")


if __name__ == "__main__":
    main()

