import sqlite3
from typing import Optional

def get_connection(db_path: str = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Apply PRAGMAs
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = DELETE;")
    conn.execute("PRAGMA synchronous = FULL;")
    conn.execute("PRAGMA secure_delete = ON;")
    conn.execute("PRAGMA trusted_schema = OFF;")
    return conn

def apply_migrations(conn: sqlite3.Connection, migrations_path: str) -> None:
    with open(migrations_path, 'r') as f:
        script = f.read()
    conn.executescript(script)
    conn.commit()
