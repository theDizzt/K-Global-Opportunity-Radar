import sqlite3
from contextlib import contextmanager
from pathlib import Path

from config.settings import DATABASE_PATH


@contextmanager
def get_connection(database_path: str | Path = DATABASE_PATH):
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
