from datetime import datetime, timezone
import re
import time
from typing import Any, Dict, List, Optional
import requests

from backend.config import ASPECT_MODEL_PATH, SENTIMENT_MODEL_PATH
from backend.database import get_connection, refresh_game_aspect_stats
from backend.ml_pipeline import ReviewAnalysisPipeline


class SteamReviewsClient:
    GET_APP_REVIEWS_URL = "https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/"
    STORE_REVIEWS_URL = "https://store.steampowered.com/appreviews/{app_id}"
    APPDETAILS_URL = "https://store.steampowered.com/api/appdetails"

    FILTER_HELPFUL = 0
    FILTER_RECENT = 1
    REVIEW_TYPE_ALL = 0
    PURCHASE_TYPE_ALL = 1

    def __init__(self, timeout: int, max_retries: int):
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "SteamAnalysisService/1.0"})

    def fetch_game_name(self, app_id: int) -> str:
        resp = self.session.get(
            self.APPDETAILS_URL, params={"appids": app_id}, timeout=self.timeout
        )
        if resp.status_code == 200:
            app_data = resp.json().get(str(app_id), {})
            if app_data.get("success") and "data" in app_data:
                return app_data["data"].get("name", f"Steam App {app_id}")
        return f"Steam App {app_id}"

    @staticmethod
    def _is_meaningful_review(text: str) -> bool:
        if not text or len(text) < 25:
            return False
        if re.search(r"[░▒▓█▄▀■□▪▫▬▲►▼◄◊○●◘◙⠀-⣿]{4,}", text):
            return False
        words = re.findall(r"[A-Za-z]{2,}", text)
        return len(words) >= 5

    def get_total_english_reviews(self, app_id: int) -> int:
        params = {
            "appid": app_id,
            "filter": self.FILTER_HELPFUL,
            "languages[0]": "english",
            "day_range": 0,
            "review_type": self.REVIEW_TYPE_ALL,
            "purchase_type": self.PURCHASE_TYPE_ALL,
            "filter_offtopic_activity": "true",
            "num_per_page": 1,
            "cursor": "*",
        }
        resp = self.session.get(
            self.GET_APP_REVIEWS_URL, params=params, timeout=self.timeout
        )
        if resp.status_code == 200:
            payload = resp.json()
            inner = payload.get("response", payload)
            summary = inner.get("query_summary", {})
            if "total_reviews" in summary:
                return int(summary["total_reviews"])
            if "total_matching" in inner:
                return int(inner["total_matching"])

        store_resp = self.session.get(
            self.STORE_REVIEWS_URL.format(app_id=app_id),
            params={"json": 1, "language": "english", "num_per_page": 1, "purchase_type": "all"},
            timeout=self.timeout,
        )
        if store_resp.status_code == 200:
            return int(store_resp.json().get("query_summary", {}).get("total_reviews", 0))
        return 0

    def fetch_recent_reviews(
        self,
        app_id: int,
        max_reviews: int,
        helpful_only: bool,
        min_playtime_hours: int,
    ) -> List[Dict[str, Any]]:
        reviews_collected: List[Dict[str, Any]] = []
        raw_inspected = 0
        cursor = "*"
        seen_cursors = set()
        max_raw_to_inspect = int(max_reviews * 1.3)

        while len(reviews_collected) < max_reviews and raw_inspected < max_raw_to_inspect:
            if cursor in seen_cursors:
                break
            seen_cursors.add(cursor)

            num_per_page = min(100, max_reviews - len(reviews_collected))

            params: Dict[str, Any] = {
                "appid": app_id,
                "filter": self.FILTER_HELPFUL if helpful_only else self.FILTER_RECENT,
                "languages[0]": "english",
                "day_range": 0,
                "cursor": cursor,
                "review_type": self.REVIEW_TYPE_ALL,
                "purchase_type": self.PURCHASE_TYPE_ALL,
                "num_per_page": num_per_page,
                "filter_offtopic_activity": "true",
                "use_review_quality": "true",
                "playtime_min_hours": min_playtime_hours,
            }

            inner_data = None
            for attempt in range(1, self.max_retries + 1):
                try:
                    resp = self.session.get(
                        self.GET_APP_REVIEWS_URL,
                        params=params,
                        timeout=self.timeout,
                    )
                    if resp.status_code == 429:
                        wait_sec = 5.0 * attempt
                        time.sleep(wait_sec)
                        continue

                    resp.raise_for_status()
                    payload = resp.json()
                    inner_data = payload.get("response", payload)
                    break
                except requests.RequestException as e:
                    if attempt == self.max_retries:
                        raise RuntimeError(
                            f"Ошибка Steam GetAppReviews/v1 для app_id={app_id}: {e}"
                        )
                    time.sleep(2.0 * attempt)

            if not inner_data:
                break

            batch = inner_data.get("reviews", [])
            if not batch:
                break

            for item in batch:
                raw_inspected += 1
                rev_text = (item.get("review") or "").strip()

                if not self._is_meaningful_review(rev_text):
                    continue

                lang = item.get("language")
                if lang and lang != "english":
                    continue

                reviews_collected.append(
                    {
                        "review_id": int(item["recommendationid"]),
                        "app_id": int(app_id),
                        "review_score": 1 if item.get("voted_up") else -1,
                        "review_votes": int(item.get("votes_up", 0)),
                        "review_date": datetime.fromtimestamp(
                            int(item.get("timestamp_created", 0)), tz=timezone.utc
                        ).isoformat(),
                        "review_text": rev_text,
                    }
                )
                if len(reviews_collected) >= max_reviews:
                    break

            next_cursor = inner_data.get("cursor")
            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor

        return reviews_collected


class IncrementalUpdateService:
    def __init__(
        self,
        steam_client: Optional[SteamReviewsClient] = None,
        pipeline: Optional[ReviewAnalysisPipeline] = None,
    ):
        self.steam_client = steam_client or SteamReviewsClient(timeout=15, max_retries=4)
        self._pipeline = pipeline

    @property
    def pipeline(self) -> ReviewAnalysisPipeline:
        if self._pipeline is None:
            self._pipeline = ReviewAnalysisPipeline(
                ASPECT_MODEL_PATH, SENTIMENT_MODEL_PATH
            )
        return self._pipeline

    def update_games(
        self, app_ids: List[int], max_sentences_per_game: int = 5000
    ) -> Dict[str, Any]:
        conn = get_connection()
        with conn:
            cur = conn.execute(
                "INSERT INTO update_runs (status, games_processed, reviews_added) VALUES ('running', 0, 0);"
            )
            run_id = cur.lastrowid

        games_processed = 0
        total_new_reviews = 0
        total_new_sentences = 0
        total_new_aspects = 0

        try:
            for app_id in app_ids:
                row = conn.execute(
                    "SELECT name FROM games WHERE app_id = ?;", (app_id,)
                ).fetchone()
                if not row:
                    game_name = self.steam_client.fetch_game_name(app_id)
                    with conn:
                        conn.execute(
                            "INSERT OR IGNORE INTO games (app_id, name) VALUES (?, ?);",
                            (app_id, game_name),
                        )

                approx_reviews_needed = int(max_sentences_per_game * 0.35) + 200
                fetched_reviews = self.steam_client.fetch_recent_reviews(
                    app_id, max_reviews=approx_reviews_needed, helpful_only=True, min_playtime_hours=1
                )
                if not fetched_reviews:
                    games_processed += 1
                    continue

                fetched_ids = [r["review_id"] for r in fetched_reviews]
                existing_ids = set()
                for i in range(0, len(fetched_ids), 900):
                    chunk = fetched_ids[i : i + 900]
                    placeholders = ",".join(["?"] * len(chunk))
                    existing_rows = conn.execute(
                        f"SELECT review_id FROM reviews WHERE review_id IN ({placeholders});",
                        chunk,
                    ).fetchall()
                    existing_ids.update(r[0] for r in existing_rows)

                new_reviews = [
                    r for r in fetched_reviews if r["review_id"] not in existing_ids
                ]

                if not new_reviews:
                    with conn:
                        conn.execute(
                            "UPDATE games SET last_updated_at = CURRENT_TIMESTAMP WHERE app_id = ?;",
                            (app_id,),
                        )
                    games_processed += 1
                    continue

                sentences = self.pipeline.split_reviews_into_sentences(new_reviews)
                if len(sentences) > max_sentences_per_game:
                    sentences = sentences[:max_sentences_per_game]
                    allowed_review_ids = {s["review_id"] for s in sentences}
                    new_reviews = [r for r in new_reviews if r["review_id"] in allowed_review_ids]

                sentences, sentiment_records = self.pipeline.analyze_sentences(sentences)

                with conn:
                    conn.executemany(
                        """INSERT OR IGNORE INTO reviews (review_id, app_id, review_score, review_votes, review_date)
                           VALUES (?, ?, ?, ?, ?);""",
                        [
                            (
                                r["review_id"],
                                r["app_id"],
                                r["review_score"],
                                r["review_votes"],
                                r["review_date"],
                            )
                            for r in new_reviews
                        ],
                    )

                    conn.executemany(
                        """INSERT OR IGNORE INTO sentences (review_id, position, sentence_text, has_aspects)
                           VALUES (?, ?, ?, ?);""",
                        [
                            (
                                s["review_id"],
                                s["position"],
                                s["sentence_text"],
                                s["has_aspects"],
                            )
                            for s in sentences
                        ],
                    )

                    new_rev_ids = [r["review_id"] for r in new_reviews]
                    id_map = {}
                    for i in range(0, len(new_rev_ids), 900):
                        chunk = new_rev_ids[i : i + 900]
                        ph = ",".join(["?"] * len(chunk))
                        s_rows = conn.execute(
                            f"SELECT review_id, position, sentence_id FROM sentences WHERE review_id IN ({ph});",
                            chunk,
                        ).fetchall()
                        for r in s_rows:
                            id_map[(r[0], r[1])] = r[2]

                    aspect_rows = [
                        (
                            id_map[(rec["review_id"], rec["position"])],
                            rec["aspect"],
                            rec["sentiment"],
                        )
                        for rec in sentiment_records
                        if (rec["review_id"], rec["position"]) in id_map
                    ]

                    conn.executemany(
                        """INSERT OR IGNORE INTO aspect_sentiments (sentence_id, aspect, sentiment)
                           VALUES (?, ?, ?);""",
                        aspect_rows,
                    )

                    conn.execute(
                        "UPDATE games SET last_updated_at = CURRENT_TIMESTAMP WHERE app_id = ?;",
                        (app_id,),
                    )
                    refresh_game_aspect_stats(conn, app_id)

                games_processed += 1
                total_new_reviews += len(new_reviews)
                total_new_sentences += len(sentences)
                total_new_aspects += len(aspect_rows)

            with conn:
                conn.execute(
                    """UPDATE update_runs
                       SET finished_at = CURRENT_TIMESTAMP,
                           status = 'success',
                           games_processed = ?,
                           reviews_added = ?
                       WHERE run_id = ?;""",
                    (games_processed, total_new_reviews, run_id),
                )

            return {
                "run_id": run_id,
                "status": 'success',
                "games_processed": games_processed,
                "reviews_added": total_new_reviews,
                "sentences_added": total_new_sentences,
                "aspect_sentiments_added": total_new_aspects,
            }

        except Exception as e:
            with conn:
                conn.execute(
                    """UPDATE update_runs
                       SET finished_at = CURRENT_TIMESTAMP,
                           status = 'failed',
                           games_processed = ?,
                           reviews_added = ?,
                           error_message = ?
                       WHERE run_id = ?;""",
                    (games_processed, total_new_reviews, str(e), run_id),
                )
            raise
        finally:
            conn.close()
