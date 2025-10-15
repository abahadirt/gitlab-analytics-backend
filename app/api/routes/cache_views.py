from fastapi import APIRouter, Query, Path, Request, HTTPException
from app.services.cache_service import get_cache_status, cache_project_data, clear_project_cache

router = APIRouter()

@router.get("/cache/{project_id}")
async def get_project_cache_status(project_id: str):
    status = await get_cache_status(project_id)
    if status.get("has_cache"):
        return status
    raise HTTPException(status_code=404, detail="Project cache not found")


@router.post("/cache/{project_id}")
async def cache_project_data_endpoint(project_id: str, data: dict):
    cached_data = await cache_project_data(project_id, data)
    return {"message": "Data cached successfully", "cached_data": cached_data}


@router.delete("/cache/{project_id}")
async def clear_project_cache_endpoint(project_id: str):
    result = await clear_project_cache(project_id)
    return {"message": result}


@router.delete("/cache/")
async def clear_all_cache():
    result = await clear_project_cache()
    return {"message": result}