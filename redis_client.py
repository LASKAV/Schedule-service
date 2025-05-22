from os import environ

from dotenv import load_dotenv

import redis

load_dotenv()


class RedisClient:
    def __init__(self, host, port, password, timeout=5):
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout

    def _get_connection(self):
        return redis.Redis(
            host=self.host,
            port=self.port,
            password=self.password,
            decode_responses=True,
            socket_timeout=self.timeout,
        )

redis_instance = RedisClient(
    host=environ.get("REDIS_HOST", "localhost"),
    port=environ.get("REDIS_PORT", "6379"),
    password=environ.get("REDIS_PASSWORD", ""),
    timeout=5,
)