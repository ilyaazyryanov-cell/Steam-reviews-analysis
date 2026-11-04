import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_PATH = Path(os.getenv("STEAM_DB_PATH", BASE_DIR / "data" / "steam_analysis.db"))
ASPECT_MODEL_PATH = Path(os.getenv("ASPECT_MODEL_PATH", BASE_DIR / "models" / "aspect_detector_bge_silver.joblib"))
SENTIMENT_MODEL_PATH = Path(os.getenv("SENTIMENT_MODEL_PATH", BASE_DIR / "models" / "sentiment_classifier_mpnet_aspect_conditioned.joblib"))
PARQUET_SENTIMENT_DIR = Path(os.getenv("PARQUET_SENTIMENT_DIR", "/home/gust/steam-llm/steam_sentiment_predictions"))

CANONICAL_ASPECTS = [
    "Audio",
    "Combat",
    "Content & Replayability",
    "Controls",
    "Developer Support & Modding",
    "Difficulty",
    "Enemies",
    "Gameplay",
    "Graphics & Art Style",
    "Level Design",
    "Multiplayer",
    "Performance",
    "Progression",
    "Story, Characters & Lore",
    "Value & Monetization",
]
