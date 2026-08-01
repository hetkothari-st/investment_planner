from pydantic_settings import BaseSettings, SettingsConfigDict

NICHES = ["memes", "finance", "facts"]

# Per-niche subreddit list for the Reddit rising ingest (spec §5).
NICHE_SUBREDDITS: dict[str, list[str]] = {
    "memes": ["memes", "dankmemes", "IndianDankMemes"],
    "finance": ["IndiaInvestments", "personalfinanceindia", "IndianStockMarket"],
    "facts": ["todayilearned", "interestingasfuck", "Damnthatsinteresting"],
}

NICHE_CACHE_TTL_SECONDS = 7 * 24 * 3600


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+psycopg://pipeline:pipeline@localhost:5432/content_pipeline"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"

    anthropic_api_key: str = ""
    niche_model: str = "claude-opus-5"

    youtube_api_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "content-pipeline/0.1"

    pexels_api_key: str = ""
    pixabay_api_key: str = ""

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    public_media_base_url: str = ""


settings = Settings()
