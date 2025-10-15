from fastapi import APIRouter, Query, Path, Request, HTTPException
from app.services.issue_service import fetch_issues_async
from app.services.repository_service import fetch_top_repositories, search_repositories_async, fetch_user_repositories, \
    repository_details

router = APIRouter()

@router.get("/top-repositories/")
async def top_repositories(request: Request):
    try:
        return await fetch_top_repositories(request)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@router.get("/search-repositories/{search_term}")
async def search_repositories(search_term: str, request: Request):
    try:
        return await search_repositories_async(request, search_term)
    except HTTPException as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@router.get("/repository-details/{project_id}")
async def repo_details(request: Request, project_id: int):
    try:
        return await repository_details(request, project_id)
    except HTTPException as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@router.get("/user-repositories/")
async def user_repositories(request: Request):
    try:
        return await fetch_user_repositories(request)
    except HTTPException as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@router.post("/store-token/")
async def store_token(request: Request, token: str):
    request.session["gitlab_token"] = token
    return {"message": "Token saved in session"}