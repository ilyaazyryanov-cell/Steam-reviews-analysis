import sqlite3
from pathlib import Path


DATABASE_PATH = Path(__file__).parent.parent / "data" / "steam_analysis.db"


def get_connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DATABASE_PATH)


def init_database():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS aspect_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            aspect TEXT NOT NULL,
            positive_mentions INTEGER NOT NULL,
            negative_mentions INTEGER NOT NULL,
            neutral_mentions INTEGER NOT NULL,
            FOREIGN KEY (game_id) REFERENCES games(id)
        )
    """)

    connection.commit()
    connection.close()