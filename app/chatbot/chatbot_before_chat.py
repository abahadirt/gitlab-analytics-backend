import httpx


async def get_full_path_from_id_rest(project_id,gitlab_token):
    GITLAB_API_URL = "https://gitlab.com/api/v4"
    headers = {}
    user_gitlab_token = None
    effective_token = gitlab_token

    if effective_token:
        headers["PRIVATE-TOKEN"] = effective_token
    else:
        print("BEKLENMEDIK OLAY: get_full_path_from_id_rest FONKSIYONUNA GITLAB_TOKEN NONE GITTI")
    async with httpx.AsyncClient() as client: # DUZENLEME: httpx fonksiyonu backende göre değişmeli(?)
        url = f"{GITLAB_API_URL}/projects/{project_id}"
        response = await client.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data["path_with_namespace"]
        else:
            print(f"get_full_path_from_id_rest returns: {response.status_code} -> {response.text}")
            return None


