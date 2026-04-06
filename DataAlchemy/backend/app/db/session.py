from pathlib import Path
import sqlite3


DB_PATH = Path(__file__).resolve().parent / "dataalchemy.db"


def get_connection() -> sqlite3.Connection:
	conn = sqlite3.connect(DB_PATH)
	conn.row_factory = sqlite3.Row
	return conn
