from pydantic import StrictStr, StrictInt
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    redis_host: StrictStr = "ropa-redis"
    redis_port: StrictInt = 6379
    redis_db: StrictInt = 0


config = Config()
