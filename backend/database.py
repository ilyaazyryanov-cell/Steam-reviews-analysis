import sqlite3
from contextlib import closing
from backend.config import DATABASE_PATH

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS games (
    app_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    header_image TEXT,
    short_description TEXT,
    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reviews (
    review_id INTEGER PRIMARY KEY,
    app_id INTEGER NOT NULL,
    review_score INTEGER NOT NULL,
    review_votes INTEGER DEFAULT 0,
    review_date TIMESTAMP NULL,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (app_id) REFERENCES games(app_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sentences (
    sentence_id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id INTEGER NOT NULL,
    position INTEGER NOT NULL,
    sentence_text TEXT NOT NULL,
    has_aspects INTEGER NOT NULL DEFAULT 0,
    UNIQUE (review_id, position),
    FOREIGN KEY (review_id) REFERENCES reviews(review_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS aspect_sentiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sentence_id INTEGER NOT NULL,
    aspect TEXT NOT NULL,
    sentiment INTEGER NOT NULL CHECK (sentiment IN (-1, 0, 1)),
    UNIQUE (sentence_id, aspect),
    FOREIGN KEY (sentence_id) REFERENCES sentences(sentence_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS aspect_stats (
    game_id INTEGER NOT NULL,
    aspect TEXT NOT NULL,
    positive_mentions INTEGER NOT NULL DEFAULT 0,
    negative_mentions INTEGER NOT NULL DEFAULT 0,
    neutral_mentions INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (game_id, aspect),
    FOREIGN KEY (game_id) REFERENCES games(app_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS update_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed')),
    games_processed INTEGER DEFAULT 0,
    reviews_added INTEGER DEFAULT 0,
    error_message TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_games_name ON games(name);
CREATE INDEX IF NOT EXISTS idx_reviews_app_id ON reviews(app_id);
CREATE INDEX IF NOT EXISTS idx_sentences_review_id ON sentences(review_id);
CREATE INDEX IF NOT EXISTS idx_aspect_sentiments_sentence_id ON aspect_sentiments(sentence_id);
CREATE INDEX IF NOT EXISTS idx_aspect_sentiments_aspect_sentiment ON aspect_sentiments(aspect, sentiment);
CREATE INDEX IF NOT EXISTS idx_aspect_stats_aspect ON aspect_stats(aspect);
"""


def get_connection() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_database():
    with closing(get_connection()) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()


def refresh_game_aspect_stats(conn, game_id):
    conn.execute("DELETE FROM aspect_stats WHERE game_id = ?;", (game_id,))
    conn.execute(
        """
        INSERT INTO aspect_stats (game_id, aspect, positive_mentions, negative_mentions, neutral_mentions)
        SELECT
            r.app_id AS game_id,
            a.aspect AS aspect,
            SUM(CASE WHEN a.sentiment = 1 THEN 1 ELSE 0 END) AS positive_mentions,
            SUM(CASE WHEN a.sentiment = -1 THEN 1 ELSE 0 END) AS negative_mentions,
            SUM(CASE WHEN a.sentiment = 0 THEN 1 ELSE 0 END) AS neutral_mentions
        FROM aspect_sentiments a
        JOIN sentences s ON a.sentence_id = s.sentence_id
        JOIN reviews r ON s.review_id = r.review_id
        WHERE r.app_id = ?
        GROUP BY r.app_id, a.aspect;
        """,
        (game_id,),
    )
