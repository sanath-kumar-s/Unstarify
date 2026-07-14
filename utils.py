import csv
import json
from typing import List, Dict, Any, Tuple
from models import Repository

def export_to_csv(repos: List[Repository], filepath: str) -> None:
    """Exports a list of Repository objects to a CSV file."""
    headers = [
        "id", "name", "owner", "description", "language", "topics",
        "fork", "archived", "private", "created_at", "updated_at",
        "html_url", "default_branch", "avatar_url", "starred_at"
    ]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for repo in repos:
            writer.writerow([
                repo.id,
                repo.name,
                repo.owner,
                repo.description,
                repo.language,
                ",".join(repo.topics),
                repo.fork,
                repo.archived,
                repo.private,
                repo.created_at,
                repo.updated_at,
                repo.html_url,
                repo.default_branch,
                repo.avatar_url,
                repo.starred_at or ""
            ])

def export_to_json(repos: List[Repository], filepath: str) -> None:
    """Exports a list of Repository objects to a JSON file."""
    data = [repo.to_dict() for repo in repos]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def import_from_json(filepath: str) -> List[Repository]:
    """Imports a list of Repository objects from a JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("JSON root must be a list of repositories.")
    return [Repository.from_dict(item) for item in data]

def compare_repositories(imported: List[Repository], current: List[Repository]) -> List[Repository]:
    """Compares imported repositories with the current list.
    Returns a list of imported repositories that are missing from the current list (by owner and name).
    """
    current_keys = {(r.owner.lower(), r.name.lower()) for r in current}
    missing: List[Repository] = []
    for r in imported:
        key = (r.owner.lower(), r.name.lower())
        if key not in current_keys:
            missing.append(r)
    return missing
