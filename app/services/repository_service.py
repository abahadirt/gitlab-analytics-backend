from fastapi import Request, HTTPException
from app.services.gitlab_service import gitlab_request  # Assuming you've moved the logic there

async def fetch_top_repositories(request: Request):
    try:
        response = await gitlab_request(
            "/projects",
            params={"order_by": "star_count", "sort": "desc", "per_page": 10},
            request=request
        )

        if response.status_code == 200:
            data = response.json()
            return [
                {"id": repo["id"], "name": repo["name"], "star_count": repo["star_count"]}
                for repo in data
            ]
        raise HTTPException(status_code=response.status, detail="Failed to fetch repositories")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def search_repositories_async(request: Request, search_term: str):
    try:
        response = await gitlab_request("/projects", params={"search": search_term}, request=request)
        if response.status_code == 200:
            data = response.json()
            filtered_data = [{"id": repo["id"], "name": repo["name"]} for repo in data]
            return filtered_data
        raise HTTPException(status_code=response.status, detail="Failed to fetch repositories")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def repository_details(request: Request, project_id: int):
    try:
        response = await gitlab_request(f"/projects/{project_id}", request=request)
        if response.status_code == 200:
            data = response.json()
            filtered_data = {
                "id": data["id"],
                "name": data["name"],
                "description": data.get("description"),
                "created_at": data["created_at"],
                "star_count": data["star_count"],
                "archived": data["archived"],
                "last_activity_at": data["last_activity_at"],
            }
            return filtered_data
        raise HTTPException(status_code=response.status, detail="Failed to fetch repositories")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def fetch_user_repositories(request: Request):
    try:
        if 'gitlab_token' in request.session:
            response = await gitlab_request("/groups", request=request)
            if response.status_code == 200:
                groups = response.json()
                group_ids = [group['id'] for group in groups if 'id' in group]
                for group_id in group_ids:
                    projects_response = await gitlab_request(f"/groups/{group_id}/projects", request=request)
                    if projects_response.status == 200:
                        group_projects = await projects_response.json()
                        filtered_data = [{"id": repo["id"], "name": repo["name"], "star_count": repo["star_count"]} for
                                         repo in group_projects]
                        return filtered_data
            raise HTTPException(status_code=response.status, detail="Failed to fetch repositories")
        else:
            return "GitLab token can not be found."
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

