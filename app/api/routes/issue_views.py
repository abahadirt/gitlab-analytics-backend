from fastapi import APIRouter, HTTPException, Request, BackgroundTasks

from app.services.issue_service import fetch_issues_async, issue_grid_data, generate_process_map, issue_details_async

router = APIRouter()

@router.get("/fetch-issues/{project_id}")
async def fetch_issues(project_id: int, request: Request):
    try:
        return await fetch_issues_async(project_id, request)
    except HTTPException as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@router.get("/issue-grid/{project_id}")
async def issue_grid(project_id: int, request: Request):
    try:
        return await issue_grid_data(project_id, request)
    except HTTPException as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@router.get("/projects/{project_id}/process-map/")
async def process_map(project_id: int, request: Request, background_tasks: BackgroundTasks):
    try:
        return await generate_process_map(project_id, request, background_tasks)
    except HTTPException as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@router.get("/issue-details/{project_id}")
async def issue_grid(project_id: int, request: Request):
    try:
        return await issue_details_async(project_id, request)
    except HTTPException as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")