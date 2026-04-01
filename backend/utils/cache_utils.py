import json
from loguru import logger

from backend.utils.captcha_utils import _get_redis


ACTIVE_MODELS_CACHE_KEY = "models:active:list"
ACTIVE_MODELS_CACHE_TTL = 300


def get_json_cache(key: str):
    try:
        raw = _get_redis().get(key)
        if not raw:
            return None
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"[cache] get_json_cache failed key={key}: {e}")
        return None


def set_json_cache(key: str, value, ttl: int = ACTIVE_MODELS_CACHE_TTL):
    try:
        _get_redis().setex(key, ttl, json.dumps(value, ensure_ascii=False))
    except Exception as e:
        logger.warning(f"[cache] set_json_cache failed key={key}: {e}")


def delete_cache(key: str):
    try:
        _get_redis().delete(key)
    except Exception as e:
        logger.warning(f"[cache] delete_cache failed key={key}: {e}")
