from database import get_connection, init_database


def seed_database():
    init_database()

    connection = get_connection()
    cursor = connection.cursor()

    games = [
        ("Hades",),
        ("Hollow Knight",),
        ("Stardew Valley",),
    ]

    cursor.executemany(
        "INSERT OR IGNORE INTO games (name) VALUES (?)",
        games
    )

    game_stats = {
        "Hades": [
            ("Gameplay", 131, 14, 5),
            ("Graphics & Art Style", 113, 7, 0),
            ("Difficulty", 58, 16, 6),
            ("Story, Characters & Lore", 91, 5, 4),
        ],
        "Hollow Knight": [
            ("Gameplay", 116, 9, 5),
            ("Graphics & Art Style", 106, 2, 2),
            ("Difficulty", 58, 30, 7),
            ("Content & Replayability", 84, 4, 2),
        ],
        "Stardew Valley": [
            ("Gameplay", 171, 5, 4),
            ("Audio", 64, 4, 2),
            ("Content & Replayability", 155, 3, 2),
            ("Value & Monetization", 98, 1, 1),
        ],
    }

    for game_name, stats in game_stats.items():
        cursor.execute(
            "SELECT id FROM games WHERE name = ?",
            (game_name,)
        )

        game_id = cursor.fetchone()[0]

        for stat in stats:
            cursor.execute(
                """
                INSERT INTO aspect_stats (
                    game_id,
                    aspect,
                    positive_mentions,
                    negative_mentions,
                    neutral_mentions
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (game_id, *stat)
            )

    connection.commit()
    connection.close()

    print("Database seeded successfully.")


if __name__ == "__main__":
    seed_database()