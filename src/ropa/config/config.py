from pydantic import StrictStr, StrictInt
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    redis_host: StrictStr = "ropa-redis"
    redis_port: StrictInt = 6379
    redis_db: StrictInt = 0

    mongodb_dsn: StrictStr = "mongodb://ropa-mongo:27017"
    mongodb_db_name: StrictStr = "ropa"


config = Config()
