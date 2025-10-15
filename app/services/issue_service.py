from fastapi import HTTPException, Request
import asyncio
import httpx
from datetime import datetime
from typing import List, Dict, Any
from starlette.background import BackgroundTasks
from app.services.cache_service import get_cached_data, cache_project_data
from app.services.gitlab_service import gitlab_request
from app.services.process_mining_service import run_process_mining

# Function to fetch issues from GitLab and process them
async def fetch_issues_async(project_id: int, request: Request) -> Dict:
    try:
        # Try to get data from cache first
        cached_data = await get_cached_data(project_id)
        if cached_data:
            return {
                "grouped_issues": cached_data["grouped_issues"],
                "issue_metrics": cached_data["issue_metrics"],
            }

        # If no cached data, fetch from GitLab
        all_issues = []
        issue_statistics_response = await gitlab_request(f"/projects/{project_id}/issues_statistics")
        if issue_statistics_response.status_code != 200:
            raise HTTPException(status_code=issue_statistics_response.status_code, detail="Failed to fetch issues")

        issue_statistics = issue_statistics_response.json()
        total_issues_count = 10000 if issue_statistics["statistics"]["counts"]["all"] > 10000 else issue_statistics["statistics"]["counts"]["all"]
        total_pages = (total_issues_count // 100) + (1 if total_issues_count % 100 > 0 else 0)

        issues_pages = await asyncio.gather(*[fetch_page_issues(page, project_id) for page in range(1, total_pages + 1)])
        for issues in issues_pages:
            all_issues.extend(issues)

        closed_issues = [issue for issue in all_issues if issue["state"] == "closed"]
        closure_times = calculate_closure_times(closed_issues)
        avg_closure_time = sum(closure_times) / len(closure_times) if closure_times else 0
        avg_closure_time_formatted = format_duration(avg_closure_time)

        exceeded_avg_time_issues = get_exceeded_avg_time_issues(all_issues, avg_closure_time)

        # Group issues by state and month
        grouped_issues = group_issues_by_state_and_month(all_issues)

        # Prepare the initial response
        initial_response = {
            "grouped_issues": grouped_issues,
            "issue_metrics": {
                "average_closure_time": avg_closure_time_formatted,
                "average_closure_time_seconds": avg_closure_time,
                "open_issues_exceeding_average": {
                    "count": len(exceeded_avg_time_issues)
                },
                "closed_issues_metrics": {
                    "closed_earlier_than_average": {
                        "count": len([issue for issue in closed_issues if (datetime.strptime(issue["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ") - datetime.strptime(issue["closed_at"], "%Y-%m-%dT%H:%M:%S.%fZ")).total_seconds() < avg_closure_time]),
                    },
                    "closed_later_than_average": {
                        "count": len([issue for issue in closed_issues if (datetime.strptime(issue["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ") - datetime.strptime(issue["closed_at"], "%Y-%m-%dT%H:%M:%S.%fZ")).total_seconds() >= avg_closure_time]),
                    }
                }
            },
            "status": "processing"
        }

        # Cache all data for further processing
        cache_data = {
            **initial_response,
            "_cached_data": {
                "all_issues": all_issues,
                "exceeded_avg_time_issues": exceeded_avg_time_issues,
                "needs_processing": True
            }
        }

        await cache_project_data(project_id, cache_data)
        return initial_response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while processing issues: {str(e)}")

async def issue_grid_data(project_id: int, request: httpx.Request) -> Dict:
    try:
        cached_data = await get_cached_data(project_id)
        if not cached_data or "_cached_data" not in cached_data:
            return {"error": "No cached data found. Please fetch project data first."}

        all_issues = cached_data["_cached_data"]["all_issues"]
        issue_grid = [
            {
                "iid": issue["iid"],
                "title": issue["title"],
                "created_at": issue["created_at"],
                "state": issue["state"],
                "author_name": issue["author"]["name"] if issue.get("author") else "Unknown",
                "merge_request_count": issue.get("merge_requests_count", 0),
            }
            for issue in all_issues
        ]
        return {"issue_grid": issue_grid}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Function to generate process map of selected project
async def generate_process_map(project_id: int, request: Any, background_tasks: BackgroundTasks):
    try:
        cached_data = await get_cached_data(project_id)
        if not cached_data or "_cached_data" not in cached_data:
            closed_issues = []
            issue_statistics_response = await gitlab_request(f"/projects/{project_id}/issues_statistics")
            if issue_statistics_response.status_code != 200:
                raise HTTPException(status_code=issue_statistics_response.status_code, detail="Failed to fetch issues")

            issue_statistics = issue_statistics_response.json()
            total_issues_count = 200 if issue_statistics["statistics"]["counts"]["closed"] > 200 else issue_statistics["statistics"]["counts"]["closed"]
            total_pages = (total_issues_count // 100) + (1 if total_issues_count % 100 > 0 else 0)

            issues_pages = await asyncio.gather(*[fetch_page_issues(page, project_id) for page in range(1, total_pages + 1)])
            for issues in issues_pages:
                closed_issues.extend(issues)

            pm_path, top_paths_with_durations = await create_process_map_and_cache(closed_issues, project_id, request,
                                                                             cached_data, background_tasks)
            return {"process_map": pm_path, "top_paths_with_durations": top_paths_with_durations}

        if not cached_data["_cached_data"].get("needs_processing", False):
            process_map = cached_data.get("process_map"),
            top_paths_with_durations = cached_data.get("top_paths_with_durations", [])
            return {"process_map": process_map, "top_paths_with_durations": top_paths_with_durations}

        all_issues = cached_data["_cached_data"]["all_issues"]

        # Limit issues to closed ones
        limited_issues = [issue for issue in all_issues if issue["state"] == "closed"][:500]
        pm_path, top_paths_with_durations = await create_process_map_and_cache(limited_issues, project_id, request, cached_data, background_tasks)
        return {"process_map": pm_path, "top_paths_with_durations": top_paths_with_durations}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while processing issues: {str(e)}")

async def issue_details_async(project_id: int, request: httpx.Request) -> Dict:
    try:
        cached_data = await get_cached_data(project_id)
        if not cached_data or "_cached_data" not in cached_data:
            return {"error": "No cached data found. Please fetch project data first."}

        return {
            "all_issues": cached_data["_cached_data"]["all_issues"],
            "closed_earlier": cached_data["_cached_data"]["closed_earlier"],
            "closed_later": cached_data["_cached_data"]["closed_later"],
            "exceeded_avg_time_issues": cached_data["_cached_data"]["exceeded_avg_time_issues"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Helper method to calculate closure times for closed issues
def calculate_closure_times(closed_issues: List[Dict]) -> List[float]:
    closure_times = []
    for issue in closed_issues:
        try:
            if issue.get("created_at") and issue.get("closed_at"):
                created_at = datetime.strptime(issue["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ")
                closed_at = datetime.strptime(issue["closed_at"], "%Y-%m-%dT%H:%M:%S.%fZ")
                closure_time = (closed_at - created_at).total_seconds()
                closure_times.append(closure_time)
        except (ValueError, KeyError):
            continue
    return closure_times

# Helper method to get the list of issues that exceed the average closure time
def get_exceeded_avg_time_issues(all_issues: List[Dict], avg_closure_time: float) -> List[int]:
    exceeded_avg_time_issues = []
    for issue in all_issues:
        if issue["state"] == "opened":
            try:
                created_at = datetime.strptime(issue["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ")
                current_duration = (datetime.now() - created_at).total_seconds()
                if current_duration > avg_closure_time:
                    exceeded_avg_time_issues.append(issue["iid"])
            except (ValueError, KeyError):
                continue
    return exceeded_avg_time_issues

# Helper method to group issues by their state and month
def group_issues_by_state_and_month(all_issues: List[Dict]) -> Dict:
    grouped_issues = {"opened": {}, "closed": {}}
    for issue in all_issues:
        try:
            state = issue["state"]
            created_at = issue["created_at"][:7]  # Extract "YYYY-MM" format
            if created_at not in grouped_issues[state]:
                grouped_issues[state][created_at] = 0
            grouped_issues[state][created_at] += 1
        except (KeyError, IndexError):
            continue
    return grouped_issues

# Helper method to fetch issues for a given page
async def fetch_page_issues(page: int, project_id: int) -> List[Dict]:
    response = await gitlab_request(f"/projects/{project_id}/issues", params={"per_page": 100, "page": page})
    if response.status_code == 200:
        return response.json()
    return []

# Helper method to fetch and process merge requests related to an issue
async def fetch_merge_requests(issue: Dict, project_id: int, request: httpx.Request) -> tuple[dict, Any] | list[Any]:
    try:
        response = await gitlab_request(
            f"/projects/{project_id}/issues/{issue['iid']}/related_merge_requests", request=request
        )
        if response.status_code == 200:
            return issue, response.json()
        return issue, []

    except Exception as e:
        return issue, []

# Helper method to format duration in a human-readable format
def format_duration(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours} hours {minutes} minutes"

#Helper method to create process map and cache result
async def create_process_map_and_cache(issue_list, project_id, request: httpx.Request, cached_data, background_tasks) -> tuple[str, list[Any]]:
    # Fetch merge requests for issues with merge requests
    issues_with_mrs = await asyncio.gather(
        *[fetch_merge_requests(issue, project_id, request) for issue in issue_list if
          issue.get("merge_requests_count", 0) > 0]
    )

    # Collect event models for processing
    event_models = generate_event_models_with_mrs(issues_with_mrs)

    # If there are fewer than 30 events, process additional issues without merge requests
    if len(event_models) < 30:
        issues_without_mrs = [issue for issue in issue_list if issue.get("merge_requests_count", 0) == 0][:200]
        event_models = generate_event_models_without_mrs(event_models, issues_without_mrs)

    # Sort event models by timestamp
    try:
        event_models.sort(
            key=lambda e: datetime.strptime(e["timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ") if e[
                                                                                            "timestamp"] != "Unknown" else datetime.min
        )
    except Exception:
        pass  # Sorting failed, proceed with unsorted

    # If no event models exist, update cache and return empty process map data
    if not event_models:
        cached_data["process_map"] = None
        cached_data["top_paths_with_durations"] = []
        cached_data["event_log"] = []
        cached_data["_cached_data"]["needs_processing"] = False
        await cache_project_data(project_id, cached_data)

        return None, []

    # Run process mining to generate process map and top paths
    pm_path, top_paths_with_durations = await run_process_mining(project_id, event_models, background_tasks)

    if cached_data:
        # Update cache with process map data
        cached_data["process_map"] = pm_path
        cached_data["top_paths_with_durations"] = top_paths_with_durations
        cached_data["event_log"] = event_models
        cached_data["_cached_data"]["needs_processing"] = False
        await cache_project_data(project_id, cached_data)

    return pm_path, top_paths_with_durations

#Helper method to generate event models with merge requests
def generate_event_models_with_mrs(issues_with_mrs):
    event_models = []
    for issue, related_mrs in issues_with_mrs:
        try:
            issue_id = issue["iid"]
            # Issue Events
            event_models.append({
                "issue_id": issue_id,
                "activity": "issue_created",
                "timestamp": issue.get("created_at", "Unknown"),
                "user": issue.get("author", {}).get("username", "Unknown"),
            })
            event_models.append({
                "issue_id": issue_id,
                "activity": "issue_updated",
                "timestamp": issue.get("updated_at", "Unknown"),
                "user": issue.get("author", {}).get("username", "Unknown"),
            })
            if "closed_at" in issue and issue["closed_at"]:
                event_models.append({
                    "issue_id": issue_id,
                    "activity": "issue_closed",
                    "timestamp": issue["closed_at"],
                    "user": issue.get("closed_by", {}).get("username", "Unknown"),
                })

            for mr in related_mrs:
                event_models.extend([
                    {
                        "issue_id": issue_id,
                        "merge_request_id": mr.get("iid", "Unknown"),
                        "activity": "merge_request_created",
                        "timestamp": mr.get("created_at", "Unknown"),
                        "user": mr.get("author", {}).get("username", "Unknown"),
                    },
                    {
                        "issue_id": issue_id,
                        "merge_request_id": mr.get("iid", "Unknown"),
                        "activity": "merge_request_updated",
                        "timestamp": mr.get("updated_at", "Unknown"),
                        "user": mr.get("author", {}).get("username", "Unknown"),
                    },
                ])
        except Exception:
            continue
    return event_models

#Helper method to generate event models without merge requests
def generate_event_models_without_mrs(event_models, issues):
    for issue in issues:
        try:
            issue_id = issue["iid"]
            event_models.append({
                "issue_id": issue_id,
                "activity": "issue_created",
                "timestamp": issue.get("created_at", "Unknown"),
                "user": issue.get("author", {}).get("username", "Unknown"),
            })
            event_models.append({
                "issue_id": issue_id,
                "activity": "issue_updated",
                "timestamp": issue.get("updated_at", "Unknown"),
                "user": issue.get("author", {}).get("username", "Unknown"),
            })
            if "closed_at" in issue and issue["closed_at"]:
                event_models.append({
                    "issue_id": issue_id,
                    "activity": "issue_closed",
                    "timestamp": issue["closed_at"],
                    "user": issue.get("closed_by", {}).get("username", "Unknown"),
                })
        except Exception:
            continue
    return event_models