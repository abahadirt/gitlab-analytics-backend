import os
from datetime import datetime
from collections import Counter
import pandas as pd
from fastapi import BackgroundTasks
from pm4py.algo.discovery.dfg import algorithm as dfg_discovery
from pm4py.visualization.dfg import visualizer as dfg_visualizer
from app.settings import settings


async def run_process_mining(pid: int, issues: list, background_tasks: BackgroundTasks):
    if not issues:
        return None, []

    data = [{
        "case:concept:name": issue["issue_id"],
        "concept:name": issue["activity"],
        "time:timestamp": issue["timestamp"],
        "user": issue["user"],
        "merge_request_id": issue.get("merge_request_id", "N/A")
    } for issue in issues]

    df = pd.DataFrame(data)
    df["time:timestamp"] = pd.to_datetime(df["time:timestamp"], utc=True)

    top_paths = get_top_paths(df)
    top_paths_with_durations = calculate_average_duration_per_path(df, top_paths)

    # Process map visualization
    dfg = dfg_discovery.apply(df)
    parameters = {
        dfg_visualizer.Variants.FREQUENCY.value.Parameters.ACTIVITY_KEY: "concept:name"
    }
    gviz = dfg_visualizer.apply(dfg, parameters=parameters)

    # Save image and CSV asynchronously using BackgroundTasks
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_filename = f"pm_{timestamp}_{pid}.png"
    image_path = os.path.join(settings.MEDIA_ROOT, image_filename)

    csv_filename = f"pm_data_{timestamp}_{pid}.csv"
    csv_path = os.path.join(settings.MEDIA_ROOT, csv_filename)

    background_tasks.add_task(dfg_visualizer.save, gviz, image_path)  # Asynchronously save the process map image
    background_tasks.add_task(df.to_csv, csv_path, index=False)  # Asynchronously save the CSV

    # Generate URLs for the frontend
    image_url = f"{settings.MEDIA_URL}{image_filename}"
    csv_url = f"{settings.MEDIA_URL}{csv_filename}"

    domain = settings.DOMAIN
    full_image_url = f"{domain}{image_url}"
    full_csv_url = f"{domain}{csv_url}"

    return full_image_url, top_paths_with_durations

def get_top_paths(df, top_n=3):
    paths = df.groupby("case:concept:name")["concept:name"].apply(list)
    path_counts = Counter(tuple(path) for path in paths)
    top_paths = path_counts.most_common(top_n)
    return [{"path": list(path), "frequency": count} for path, count in top_paths]


def get_frequent_transitions(df, top_n=3):
    df = df.sort_values(by=["case:concept:name", "time:timestamp"])
    df["next_activity"] = df.groupby("case:concept:name")["concept:name"].shift(-1)
    transitions = df.dropna(subset=["next_activity"])
    transition_counts = transitions.groupby(["concept:name", "next_activity"]).size()
    top_transitions = transition_counts.nlargest(top_n).reset_index()
    top_transitions.columns = ["from_activity", "to_activity", "count"]
    return top_transitions.to_dict(orient="records")


def format_duration(seconds):
    days = int(seconds // (24 * 3600))
    remaining = seconds % (24 * 3600)
    hours = int(remaining // 3600)
    remaining %= 3600
    minutes = int(remaining // 60)
    parts = []
    if days: parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours: parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes: parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    return " ".join(parts) if parts else "less than 1 minute"


def calculate_average_duration_per_path(df, top_paths):
    durations = []
    total_cases = len(df["case:concept:name"].unique())
    for path_info in top_paths:
        path = path_info["path"]
        path_cases = df.groupby("case:concept:name").filter(
            lambda x: list(x["concept:name"]) == path
        )
        path_case_count = len(path_cases["case:concept:name"].unique())
        path_percentage = (path_case_count / total_cases * 100) if total_cases else 0

        matching_cases = path_cases.groupby("case:concept:name").filter(
            lambda x: "issue_created" in x["concept:name"].values and
                      "issue_closed" in x["concept:name"].values
        )

        case_durations = []
        for _, case_data in matching_cases.groupby("case:concept:name"):
            created_time = case_data[case_data["concept:name"] == "issue_created"]["time:timestamp"].iloc[0]
            closed_time = case_data[case_data["concept:name"] == "issue_closed"]["time:timestamp"].iloc[0]
            duration = (closed_time - created_time).total_seconds()
            case_durations.append(duration)

        avg_duration = sum(case_durations) / len(case_durations) if case_durations else 0
        durations.append({
            "path": path,
            "frequency": path_info["frequency"],
            "issue_count": path_case_count,
            "percentage_of_total": round(path_percentage, 2),
            "average_duration": float(avg_duration),
            "average_duration_days": round(avg_duration / (24 * 3600), 2),
            "duration_formatted": format_duration(avg_duration)
        })

    return sorted(durations, key=lambda x: x["average_duration"], reverse=True)[:3]
