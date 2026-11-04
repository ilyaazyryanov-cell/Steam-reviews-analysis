import sqlite3
import requests
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "steam_analysis.db"


def upgrade_db_and_backfill():
    conn = sqlite3.connect(DB_PATH)

    try:
        conn.execute("ALTER TABLE games ADD COLUMN header_image TEXT;")
        conn.execute("ALTER TABLE games ADD COLUMN short_description TEXT;")
    except sqlite3.OperationalError:
        pass

    games = conn.execute(
        "SELECT app_id FROM games WHERE header_image IS NULL OR header_image = ''"
    ).fetchall()
    print(f"Игр для загрузки метаданных: {len(games)}")

    session = requests.Session()
    for idx, (app_id,) in enumerate(games, 1):
        try:
            resp = session.get(
                f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=english",
                timeout=10,
            )
            if resp.status_code == 429:
                print("Steam API 429 rate limit. Waiting 10s...")
                time.sleep(10)
                continue

            if resp.status_code != 200:
                continue

            app_data = resp.json().get(str(app_id), {})
            if app_data.get("success") and "data" in app_data:
                d = app_data["data"]
                img = d.get("header_image", "")
                desc = d.get("short_description", "")

                conn.execute(
                    "UPDATE games SET header_image = ?, short_description = ? WHERE app_id = ?",
                    (img, desc, app_id),
                )
                conn.commit()
                print(f"[{idx}/{len(games)}] Обновлено: {d.get('name')}")

            time.sleep(1.5)
        except (requests.RequestException, sqlite3.Error, ValueError) as err:
            print(f"[{idx}/{len(games)}] Ошибка для app_id={app_id}: {err}")

    conn.close()
    print("Обновление завершено.")


if __name__ == "__main__":
    upgrade_db_and_backfill()
