import json
from datetime import datetime
import redis.asyncio as aioredis
from app.settings import settings

REDIS_URL = settings.REDIS_URL
CACHE_TIMEOUT = settings.CACHE_TIMEOUT
# Initialize Redis connection pool (this will be done once when FastAPI starts)
redis = aioredis.from_url(REDIS_URL, decode_responses=True)


# Helper function to get the cache key for a project
def get_cache_key(project_id: int) -> str:
    return f"project_data:{project_id}"


# Function to retrieve cached data for a project
async def get_cached_data(project_id: int):
    cache_key = get_cache_key(project_id)
    cached_data = await redis.get(cache_key)
    return json.loads(cached_data) if cached_data else None

# Function to cache project data with timestamp
async def cache_project_data(project_id: int, data: dict):
    cache_key = get_cache_key(project_id)
    cached_data = {
        **data,
        "cached_at": datetime.now().isoformat(),
        "project_id": project_id
    }
    await redis.set(cache_key, json.dumps(cached_data), ex=CACHE_TIMEOUT)
    return cached_data

# Function to clear cache for a specific project or all projects
async def clear_project_cache(project_id: int = None):
    if project_id:
        cache_key = get_cache_key(project_id)
        await redis.delete(cache_key)
        return f"Cache cleared for project {project_id}"

    # Clear all project caches
    keys = await redis.keys("project_data:*")
    for key in keys:
        await redis.delete(key)
    return "All project caches cleared"

# Function to get cache status for a specific project or all projects
async def get_cache_status(project_id: int = None):
    if project_id:
        cached_data = await get_cached_data(project_id)
        if cached_data:
            return {
                "project_id": project_id,
                "has_cache": True,
                "cached_at": cached_data["cached_at"],
                "cache_age": str(datetime.now() - datetime.fromisoformat(cached_data["cached_at"]))
            }
        return {"project_id": project_id, "has_cache": False}

    # Get status for all cached projects
    cache_status = {}
    keys = await redis.keys("project_data:*")
    for key in keys:
        pid = key.split(":")[-1]
        data = await get_cached_data(pid)
        if data:
            cache_status[pid] = {
                "cached_at": data["cached_at"],
                "cache_age": str(datetime.now() - datetime.fromisoformat(data["cached_at"]))
            }

    return cache_status