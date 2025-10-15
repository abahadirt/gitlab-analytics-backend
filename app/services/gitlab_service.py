import httpx
from fastapi import Request
from app.settings import settings

GITLAB_API_BASE_URL = "https://gitlab.com/api/v4"

# fallback token from env or settings
GITLAB_DEFAULT_TOKEN = settings.GITLAB_DEFAULT_TOKEN

async def gitlab_request(endpoint: str, params: dict = None, method: str = "GET", request: Request = None):
    """
    Makes an async request to the GitLab API using the appropriate token based on user login or guest access.
    """
    # Determine the token to use
    token = None
    if request:
        session_token = request.cookies.get("gitlab_token")
        token = session_token if session_token else GITLAB_DEFAULT_TOKEN
    else:
        token = GITLAB_DEFAULT_TOKEN

    headers = {
        "PRIVATE-TOKEN": token
    }

    url = f"{GITLAB_API_BASE_URL}{endpoint}"

    async with httpx.AsyncClient() as client:
        if method == "GET":
            response = await client.get(url, headers=headers, params=params)
        elif method == "POST":
            response = await client.post(url, headers=headers, json=params)
        elif method == "PUT":
            response = await client.put(url, headers=headers, json=params)
        elif method == "DELETE":
            response = await client.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

    return response
