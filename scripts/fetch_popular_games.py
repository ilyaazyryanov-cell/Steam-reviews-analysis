import re
import sys
import time
from contextlib import closing
from pathlib import Path
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.database import get_connection
from backend.steam_service import IncrementalUpdateService

MIN_TOTAL_REVIEWS_IN_STEAM = 1000
MAX_SENTENCES_PER_GAME = 5000
SKIP_IF_DB_HAS_AT_LEAST = 500
STEAMSPY_PAGES_TO_SCAN = 5


def fetch_candidates_from_steamspy(max_pages: int = 3) -> list[tuple[int, str]]:
    candidates = {}
    session = requests.Session()
    session.headers.update({"User-Agent": "SteamAnalysisBot/1.0"})

    print(f"[SteamSpy] сканирование до {max_pages * 1000} игр...")
    for page in range(max_pages):
        try:
            resp = session.get(
                "https://steamspy.com/api.php",
                params={"request": "all", "page": page},
                timeout=20,
            )
            if resp.status_code != 200:
                break
            data = resp.json()
            if not isinstance(data, dict) or not data:
                break

            items = sorted(
                data.values(),
                key=lambda x: int(x.get("positive", 0)) + int(x.get("negative", 0)),
                reverse=True,
            )
            for item in items:
                appid = int(item.get("appid", 0))
                name = str(item.get("name") or f"Steam App {appid}").strip()
                total_ratings = int(item.get("positive", 0)) + int(item.get("negative", 0))
                if appid > 0 and total_ratings >= MIN_TOTAL_REVIEWS_IN_STEAM:
                    candidates[appid] = name

            print(f"  -> страница {page + 1}/{max_pages}: кандидатов: {len(candidates)}")
            time.sleep(1.0)
        except requests.RequestException as e:
            print(f"  -> ошибка при чтении SteamSpy: {e}")
            break

    return list(candidates.items())


def fetch_candidates_from_steam_charts(max_items: int = 300) -> list[tuple[int, str]]:
    candidates = {}
    session = requests.Session()
    session.headers.update({"User-Agent": "SteamAnalysisBot/1.0"})

    print("[Steam Charts] поиск топ-продаж...")
    for start in range(0, max_items, 100):
        try:
            resp = session.get(
                "https://store.steampowered.com/search/results/",
                params={
                    "query": "",
                    "start": start,
                    "count": 100,
                    "dynamic_data": "",
                    "sort_by": "_ASC",
                    "category1": 998,
                    "filter": "topsellers",
                    "infinite": 1,
                },
                timeout=15,
            )
            if resp.status_code != 200:
                break
            html = resp.json().get("results_html", "")
            matches = re.findall(
                r'data-ds-appid="(\d+)".*?<span class="title">(.*?)</span>',
                html,
                flags=re.DOTALL,
            )
            for appid_str, title in matches:
                candidates[int(appid_str)] = title.strip()
        except (requests.RequestException, ValueError):
            break

    print(f"  -> из чартов добавлено: {len(candidates)}")
    return list(candidates.items())


def get_existing_review_counts() -> dict[int, int]:
    with closing(get_connection()) as conn:
        rows = conn.execute(
            "SELECT app_id, COUNT(*) FROM reviews GROUP BY app_id;"
        ).fetchall()
        return {int(r[0]): int(r[1]) for r in rows}


def get_steam_english_reviews_count(app_id: int) -> int:
    url = f"https://store.steampowered.com/appreviews/{app_id}"
    params = {
        "json": 1,
        "language": "english",
        "num_per_page": 1,
        "purchase_type": "all",
    }
    resp = requests.get(url, params=params, timeout=10)
    if resp.status_code == 200:
        return int(resp.json().get("query_summary", {}).get("total_reviews", 0))
    return 0


def format_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def main():
    print(f"Поиск игр: >= {MIN_TOTAL_REVIEWS_IN_STEAM} отзывов, макс {MAX_SENTENCES_PER_GAME} предложений на игру")

    db_counts = get_existing_review_counts()
    print(f"Игр в базе: {len(db_counts)}")

    merged = {}
    for app_id, name in fetch_candidates_from_steam_charts(max_items=300):
        merged[app_id] = name
    for app_id, name in fetch_candidates_from_steamspy(max_pages=STEAMSPY_PAGES_TO_SCAN):
        if app_id not in merged:
            merged[app_id] = name

    candidates = list(merged.items())
    print(f"Кандидатов для проверки: {len(candidates)}\n")

    updater = IncrementalUpdateService(steam_client=None, pipeline=None)
    processed_count = 0
    skipped_db_count = 0

    global_start_time = time.time()

    for idx, (app_id, title) in enumerate(candidates, 1):
        existing_cnt = db_counts.get(app_id, 0)
        if existing_cnt >= SKIP_IF_DB_HAS_AT_LEAST:
            skipped_db_count += 1
            continue

        total_in_steam = get_steam_english_reviews_count(app_id)
        if total_in_steam < MIN_TOTAL_REVIEWS_IN_STEAM:
            continue

        game_start_time = time.time()
        print(
            f"[{idx}/{len(candidates)}] {title} (app_id={app_id}) | "
            f"В БД: {existing_cnt} | В Steam: {total_in_steam:,}..."
        )

        try:
            res = updater.update_games([app_id], max_sentences_per_game=MAX_SENTENCES_PER_GAME)
            elapsed = time.time() - game_start_time
            processed_count += 1
            print(
                f"  -> готово за {format_time(elapsed)} "
                f"(+{res['reviews_added']} отзывов, "
                f"+{res['sentences_added']} предложений, "
                f"+{res['aspect_sentiments_added']} аспектов)"
            )
        except Exception as e:
            elapsed = time.time() - game_start_time
            print(f"  -> ошибка обработки {title} за {format_time(elapsed)}: {e}")

    total_elapsed = time.time() - global_start_time
    print(f"\nИтог за {format_time(total_elapsed)}:")
    print(f"  Обработано новых: {processed_count}")
    print(f"  Пропущено (уже в БД): {skipped_db_count}")


if __name__ == "__main__":
    main()
