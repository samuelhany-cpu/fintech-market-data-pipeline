from pathlib import Path

from sqlalchemy import text

from src.db.engine import engine

SQL_DIR = Path(__file__).parent.parent.parent / "sql"


def init_db() -> None:
    with engine.begin() as conn:
        for sql_file in sorted(SQL_DIR.glob("*.sql")):
            conn.execute(text(sql_file.read_text(encoding="utf-8")))
    print(f"[init_db] Schema and indexes applied from {SQL_DIR}")


if __name__ == "__main__":
    init_db()
