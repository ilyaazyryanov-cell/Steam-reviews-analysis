import logging
from contextlib import asynccontextmanager, closing
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.config import CANONICAL_ASPECTS
from backend.database import get_connection, init_database
from backend.steam_service import IncrementalUpdateService

logger = logging.getLogger("steam_backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    yield

app = FastAPI(title="Steam Analysis API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error on {request.method} {request.url.path}: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


updater = IncrementalUpdateService()

# Значимым считается аспект минимум с 5 примерами или 0.5% от всех
DYNAMIC_THRESHOLD_SQL = (
    "MAX(5, 0.005 * (SELECT SUM(positive_mentions + negative_mentions + neutral_mentions) "
    "FROM aspect_stats AS ast WHERE ast.game_id = {game_id_col}))"
)


class FilterItem(BaseModel):
    aspect: str
    min_positive: Optional[float] = Field(None, ge=0, le=100)
    max_negative: Optional[float] = Field(None, ge=0, le=100)


class SearchRequest(BaseModel):
    filters: List[FilterItem]
    search: str = ""
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    exclude_neutral: bool = False


class UpdateRequest(BaseModel):
    app_ids: List[int]
    max_sentences_per_game: int = Field(5000, ge=1, le=20000)


def calc_threshold(total_mentions: int) -> float:
    return max(5.0, total_mentions * 0.005)


def build_aspect_stats(pos: int, neg: int, neu: int, threshold: float, exclude_neutral: bool = False) -> dict:
    mentions = pos + neg + neu
    total = pos + neg + (0 if exclude_neutral else neu)

    if mentions < threshold or total <= 0:
        return {
            'mentions': mentions,
            'positive_percent': None,
            'negative_percent': None,
            'neutral_percent': None,
        }

    return {
        'mentions': mentions,
        'positive_percent': round(pos / total * 100, 1),
        'negative_percent': round(neg / total * 100, 1),
        'neutral_percent': 0.0 if exclude_neutral else round(neu / total * 100, 1),
    }


@app.get("/")
def get_root():
    return {"message": "Steam Analysis API is working!", "aspects": CANONICAL_ASPECTS}


@app.get("/aspects")
def get_aspects():
    return CANONICAL_ASPECTS


@app.get("/games")
def list_games(
    search: str = "",
    q: str = "",
    aspect: str = "",
    min_positive: float = Query(0, ge=0, le=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    exclude_neutral: bool = False,
):
    search_term = (q or search).strip()
    aspect_term = aspect.strip()
    offset = (page - 1) * page_size

    joins = ""
    where = ["games.name LIKE ? COLLATE NOCASE"]
    params: List[Any] = [f"%{search_term}%"]

    if aspect_term:
        total_expr = "aspect_stats.positive_mentions + aspect_stats.negative_mentions"
        if not exclude_neutral:
            total_expr += " + aspect_stats.neutral_mentions"

        joins = " JOIN aspect_stats ON games.app_id = aspect_stats.game_id "
        where.append("(aspect_stats.aspect = ? OR aspect_stats.aspect LIKE ?)")
        params += [aspect_term, f"%{aspect_term}%"]
        where.append(
            "(aspect_stats.positive_mentions + aspect_stats.negative_mentions + aspect_stats.neutral_mentions) >= "
            + DYNAMIC_THRESHOLD_SQL.format(game_id_col="games.app_id")
        )
        where.append(f"({total_expr}) > 0")
        where.append(f"CAST(aspect_stats.positive_mentions AS REAL) / ({total_expr}) * 100 >= ?")
        params.append(min_positive)

    where_sql = " WHERE " + " AND ".join(where)

    with closing(get_connection()) as db:
        total = db.execute(
            "SELECT COUNT(DISTINCT games.app_id) FROM games" + joins + where_sql, params
        ).fetchone()[0]
        rows = db.execute(
            "SELECT DISTINCT games.app_id, games.name, games.header_image, games.last_updated_at FROM games"
            + joins + where_sql
            + " ORDER BY games.name COLLATE NOCASE LIMIT ? OFFSET ?",
            params + [page_size, offset],
        ).fetchall()

    return {
        "items": [
            {
                "id": r[0],
                "app_id": r[0],
                "name": r[1],
                "header_image": r[2],
                "last_updated_at": r[3],
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "pages": (total + page_size - 1) // page_size,
    }


@app.get("/games/compare")
def compare_games(
    app_ids: List[int] = Query(default_factory=list, description="ID игр для сравнения"),
    exclude_neutral: bool = False,
):
    if not app_ids:
        return []

    placeholders = ",".join("?" * len(app_ids))
    with closing(get_connection()) as db:
        names = dict(
            db.execute(
                f"SELECT app_id, name FROM games WHERE app_id IN ({placeholders})",
                app_ids,
            ).fetchall()
        )
        stats = db.execute(
            f"SELECT game_id, aspect, positive_mentions, negative_mentions, neutral_mentions "
            f"FROM aspect_stats WHERE game_id IN ({placeholders})",
            app_ids,
        ).fetchall()

    totals = {}
    for gid, _, pos, neg, neu in stats:
        totals[gid] = totals.get(gid, 0) + (pos or 0) + (neg or 0) + (neu or 0)

    result = {
        gid: {"id": gid, "name": names.get(gid, f"App {gid}"), "aspects": {}}
        for gid in app_ids
    }

    for gid, aspect, pos, neg, neu in stats:
        threshold = calc_threshold(totals[gid])
        result[gid]["aspects"][aspect] = build_aspect_stats(
            pos or 0, neg or 0, neu or 0, threshold, exclude_neutral
        )

    return list(result.values())


@app.post("/games/advanced_search")
def search_games_advanced(req: SearchRequest):
    offset = (req.page - 1) * req.page_size
    denom = "(positive_mentions + negative_mentions)" if req.exclude_neutral else "(positive_mentions + negative_mentions + neutral_mentions)"

    final_query = "SELECT app_id FROM games WHERE name LIKE ? COLLATE NOCASE"
    params: List[Any] = [f"%{req.search.strip()}%"]

    for f in req.filters:
        aspect = f.aspect.strip()
        if not aspect:
            continue

        sub = "SELECT game_id FROM aspect_stats WHERE aspect = ?"
        params.append(aspect)

        if f.min_positive is not None or f.max_negative is not None:
            sub += (
                " AND (positive_mentions + negative_mentions + neutral_mentions) >= "
                + DYNAMIC_THRESHOLD_SQL.format(game_id_col="aspect_stats.game_id")
            )
            sub += f" AND {denom} > 0"
        if f.min_positive is not None:
            sub += f" AND CAST(positive_mentions AS REAL) / {denom} * 100 >= ?"
            params.append(f.min_positive)
        if f.max_negative is not None:
            sub += f" AND CAST(negative_mentions AS REAL) / {denom} * 100 <= ?"
            params.append(f.max_negative)

        #Intersect потому что быстрее
        final_query += " INTERSECT " + sub
    with closing(get_connection()) as db:
        total = db.execute(f"SELECT COUNT(*) FROM ({final_query})", params).fetchone()[0]
        rows = db.execute(
            f"SELECT app_id, name, header_image, last_updated_at FROM games "
            f"WHERE app_id IN ({final_query}) ORDER BY name COLLATE NOCASE LIMIT ? OFFSET ?",
            params + [req.page_size, offset],
        ).fetchall()

    return {
        "items": [
            {
                "id": r[0],
                "app_id": r[0],
                "name": r[1],
                "header_image": r[2],
                "last_updated_at": r[3],
            }
            for r in rows
        ],
        "total": total,
        "page": req.page,
        "pages": (total + req.page_size - 1) // req.page_size,
    }


@app.get("/games/{game_id}")
def get_game_details(game_id: int):
    with closing(get_connection()) as db:
        game = db.execute(
            "SELECT app_id, name, header_image, short_description, last_updated_at FROM games WHERE app_id = ?",
            (game_id,),
        ).fetchone()
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        review_count = db.execute(
            "SELECT COUNT(*) FROM reviews WHERE app_id = ?", (game_id,)
        ).fetchone()[0]

    return {
        "id": game[0],
        "app_id": game[0],
        "name": game[1],
        "header_image": game[2],
        "short_description": game[3],
        "last_updated_at": game[4],
        "total_reviews": review_count,
    }


@app.get("/games/{game_id}/aspects")
def get_game_aspects(
    game_id: int,
    exclude_neutral: bool = False,
    sort_by: str = "aspect",
    descending: bool = False,
    days: Optional[int] = Query(None, ge=1, description="Только отзывы за последние N дней"),
):
    with closing(get_connection()) as db:
        if not db.execute("SELECT 1 FROM games WHERE app_id = ?", (game_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Game not found")

        if days is None:
            rows = db.execute(
                "SELECT aspect, positive_mentions, negative_mentions, neutral_mentions "
                "FROM aspect_stats WHERE game_id = ?",
                (game_id,),
            ).fetchall()
        else:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            rows = db.execute(
                """
                SELECT a.aspect,
                       SUM(a.sentiment = 1),
                       SUM(a.sentiment = -1),
                       SUM(a.sentiment = 0)
                FROM aspect_sentiments a
                JOIN sentences s ON a.sentence_id = s.sentence_id
                JOIN reviews r ON s.review_id = r.review_id
                WHERE r.app_id = ? AND r.review_date >= ?
                GROUP BY a.aspect
                """,
                (game_id, cutoff),
            ).fetchall()

    rows = [(asp, pos or 0, neg or 0, neu or 0) for asp, pos, neg, neu in rows]
    threshold = calc_threshold(sum(pos + neg + neu for _, pos, neg, neu in rows))

    result = [
        {"aspect": asp, **build_aspect_stats(pos, neg, neu, threshold, exclude_neutral)}
        for asp, pos, neg, neu in rows
    ]

    if sort_by not in ("aspect", "mentions", "positive_percent", "negative_percent"):
        sort_by = "aspect"

    known = sorted(
        (x for x in result if x[sort_by] is not None),
        key=lambda x: x[sort_by],
        reverse=descending,
    )
    unknown = [x for x in result if x[sort_by] is None]
    return known + unknown


@app.get("/games/{game_id}/sentences")
def list_sentences(
    game_id: int,
    aspect: Optional[str] = None,
    sentiment: Optional[int] = Query(None, ge=-1, le=1),
    limit: int = Query(10, ge=1, le=50),
):
    with closing(get_connection()) as db:
        if not db.execute("SELECT 1 FROM games WHERE app_id = ?", (game_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Game not found")

        query = """
            SELECT s.sentence_id, r.review_id, s.sentence_text, a.aspect, a.sentiment, a.confidence
            FROM aspect_sentiments a
            JOIN sentences s ON a.sentence_id = s.sentence_id
            JOIN reviews r ON s.review_id = r.review_id
            WHERE r.app_id = ? AND a.confidence IS NOT NULL
        """
        params: List[Any] = [game_id]

        if aspect is not None:
            query += " AND a.aspect = ?"
            params.append(aspect)
        if sentiment is not None:
            query += " AND a.sentiment = ?"
            params.append(sentiment)

        query += " ORDER BY a.confidence DESC LIMIT ?"
        params.append(limit)

        rows = db.execute(query, params).fetchall()

    return [
        {
            "sentence_id": sid,
            "review_id": rid,
            "sentence_text": text,
            "aspect": asp,
            "sentiment": sent,
            "confidence": round(conf, 3),
        }
        for sid, rid, text, asp, sent, conf in rows
    ]


@app.post("/games/{game_id}/update")
def run_update_for_game(game_id: int, max_sentences: int = Query(5000, ge=1, le=20000)):
    return updater.update_games([game_id], max_sentences_per_game=max_sentences)


@app.post("/updates/run")
def run_update_batch(req: UpdateRequest):
    return updater.update_games(req.app_ids, max_sentences_per_game=req.max_sentences_per_game)


@app.get("/updates")
def list_updates(limit: int = Query(20, ge=1, le=100)):
    with closing(get_connection()) as db:
        rows = db.execute(
            "SELECT run_id, started_at, finished_at, status, games_processed, reviews_added, error_message "
            "FROM update_runs ORDER BY run_id DESC LIMIT ?",
            (limit,),
        ).fetchall()

    return [
        {
            "run_id": r[0],
            "started_at": r[1],
            "finished_at": r[2],
            "status": r[3],
            "games_processed": r[4],
            "reviews_added": r[5],
            "error_message": r[6],
        }
        for r in rows
    ]


@app.get("/games/{game_id}/similar")
def get_similar_games(game_id: int, limit: int = Query(8, ge=1, le=20)):
    with closing(get_connection()) as db:
        if not db.execute("SELECT 1 FROM games WHERE app_id = ?", (game_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Game not found")

        base_rows = db.execute(
            "SELECT aspect, positive_mentions, negative_mentions, neutral_mentions "
            "FROM aspect_stats WHERE game_id = ?",
            (game_id,),
        ).fetchall()
        base_rows = [(asp, p or 0, n or 0, neu or 0) for asp, p, n, neu in base_rows]

        base_threshold = calc_threshold(sum(p + n + neu for _, p, n, neu in base_rows))
        base_profile = {
            asp: p / (p + n) * 100
            for asp, p, n, neu in base_rows
            if p + n + neu >= base_threshold and p + n > 0
        }
        if not base_profile:
            return []

        other_rows = db.execute(
            "SELECT game_id, aspect, positive_mentions, negative_mentions, neutral_mentions "
            "FROM aspect_stats WHERE game_id != ?",
            (game_id,),
        ).fetchall()

        stats_by_game = {}
        for gid, asp, p, n, neu in other_rows:
            stats_by_game.setdefault(gid, []).append((asp, p or 0, n or 0, neu or 0))

        scored = []
        for gid, game_rows in stats_by_game.items():
            threshold = calc_threshold(sum(p + n + neu for _, p, n, neu in game_rows))
            shared = 0
            diff_sum = 0.0

            for asp, p, n, neu in game_rows:
                if asp in base_profile and p + n + neu >= threshold and p + n > 0:
                    shared += 1
                    diff_sum += abs(base_profile[asp] - p / (p + n) * 100)

            if shared >= 2:         #100 за сторону - разница в проценте позитивных
                score = shared * 100 - (diff_sum / shared)
                scored.append((gid, score, shared))

        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:limit]
        if not top:
            return []

        placeholders = ",".join("?" * len(top))
        meta = {
            row[0]: row
            for row in db.execute(
                f"SELECT app_id, name, header_image FROM games WHERE app_id IN ({placeholders})",
                [gid for gid, _, _ in top],
            ).fetchall()
        }

    return [
        {
            "id": gid,
            "app_id": gid,
            "name": meta[gid][1],
            "header_image": meta[gid][2],
            "shared_aspects_count": shared,
        }
        for gid, _, shared in top
        if gid in meta
    ]
