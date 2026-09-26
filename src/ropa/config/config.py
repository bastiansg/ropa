from pathlib import Path

from pydantic import StrictInt, StrictStr
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    telegram_bot_token: StrictStr | None = None
    telegram_media_timeout_seconds: StrictInt = 60

    redis_host: StrictStr = "ropa-redis"
    redis_port: StrictInt = 6379
    redis_db: StrictInt = 0

    mongodb_dsn: StrictStr = "mongodb://ropa-mongo:27017"
    mongodb_db_name: StrictStr = "ropa"

    bodym_train_directory: Path = Path("resources/datasets/bodym/train")

    gender_aliases: dict[StrictStr, StrictStr] = {
        "female": "woman",
        "male": "man",
    }


config = Config()
