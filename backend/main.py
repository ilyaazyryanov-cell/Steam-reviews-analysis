from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import get_connection, init_database

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_database()


@app.get("/")
def root():
    return {"message": "Steam Analysis API is working!"}


@app.get("/games")
def get_games(
    search: str = "",
    aspect: str = "",
    min_positive: float = 0
):
    connection = get_connection()
    cursor = connection.cursor()

    if aspect and min_positive > 0:
        cursor.execute(
            """
            SELECT
                games.id,
                games.name
            FROM games
            JOIN aspect_stats
                ON games.id = aspect_stats.game_id
            WHERE games.name LIKE ?
              AND aspect_stats.aspect = ?
              AND (
                  CAST(aspect_stats.positive_mentions AS REAL)
                  /
                  (
                      aspect_stats.positive_mentions
                      + aspect_stats.negative_mentions
                      + aspect_stats.neutral_mentions
                  )
              ) * 100 >= ?
            ORDER BY games.name
            """,
            (
                f"%{search}%",
                aspect,
                min_positive
            )
        )
    else:
        cursor.execute(
            """
            SELECT id, name
            FROM games
            WHERE name LIKE ?
            ORDER BY name
            """,
            (f"%{search}%",)
        )

    games = cursor.fetchall()
    connection.close()

    return [
        {
            "id": game[0],
            "name": game[1]
        }
        for game in games
    ]


@app.get("/games/{game_id}/aspects")
def get_game_aspects(
    game_id: int,
    exclude_neutral: bool = False,
    sort_by: str = "aspect",
    descending: bool = False
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            aspect,
            positive_mentions,
            negative_mentions,
            neutral_mentions
        FROM aspect_stats
        WHERE game_id = ?
        """,
        (game_id,)
    )

    rows = cursor.fetchall()
    connection.close()

    aspects = []

    for row in rows:
        aspect = row[0]
        positive = row[1]
        negative = row[2]
        neutral = row[3]

        if exclude_neutral:
            total = positive + negative

            if total == 0:
                positive_percent = 0
                negative_percent = 0
            else:
                positive_percent = positive / total * 100
                negative_percent = negative / total * 100

            neutral_percent = 0

        else:
            total = positive + negative + neutral

            if total == 0:
                positive_percent = 0
                negative_percent = 0
                neutral_percent = 0
            else:
                positive_percent = positive / total * 100
                negative_percent = negative / total * 100
                neutral_percent = neutral / total * 100

        if exclude_neutral:
            mentions = positive + negative
        else:
            mentions = positive + negative + neutral

        aspects.append(
            {
                "aspect": aspect,
                "mentions": mentions,
                "positive_percent": round(positive_percent, 1),
                "negative_percent": round(negative_percent, 1),
                "neutral_percent": round(neutral_percent, 1)
            }
        )

    allowed_sort_fields = {
        "aspect": "aspect",
        "mentions": "mentions",
        "positive": "positive_percent",
        "negative": "negative_percent",
        "neutral": "neutral_percent"
    }

    sort_field = allowed_sort_fields.get(sort_by, "aspect")

    aspects.sort(
        key=lambda item: item[sort_field],
        reverse=descending
    )

    return aspects