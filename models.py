from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class Repository:
    id: int
    name: str
    owner: str
    description: str
    language: str
    topics: List[str] = field(default_factory=list)
    fork: bool = False
    archived: bool = False
    private: bool = False
    created_at: str = ""
    updated_at: str = ""
    html_url: str = ""
    default_branch: str = ""
    avatar_url: str = ""
    starred_at: Optional[str] = None
    selected: bool = False

    @classmethod
    def from_api_json(cls, data: Dict[str, Any]) -> "Repository":
        """Constructs a Repository instance from the GitHub API JSON representation.
        Handles both the starred_at wrapper structure if 'repo' is present, or direct repository dictionary.
        """
        starred_at = data.get("starred_at")
        repo_data = data.get("repo") if "repo" in data else data

        owner_data = repo_data.get("owner", {})
        owner_name = owner_data.get("login", "")
        avatar_url = owner_data.get("avatar_url", "")

        return cls(
            id=repo_data.get("id", 0),
            name=repo_data.get("name", ""),
            owner=owner_name,
            description=repo_data.get("description") or "",
            language=repo_data.get("language") or "None",
            topics=repo_data.get("topics") or [],
            fork=repo_data.get("fork", False),
            archived=repo_data.get("archived", False),
            private=repo_data.get("private", False),
            created_at=repo_data.get("created_at") or "",
            updated_at=repo_data.get("updated_at") or "",
            html_url=repo_data.get("html_url") or "",
            default_branch=repo_data.get("default_branch") or "",
            avatar_url=avatar_url,
            starred_at=starred_at,
            selected=False
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts to a dictionary suitable for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "owner": self.owner,
            "description": self.description,
            "language": self.language,
            "topics": self.topics,
            "fork": self.fork,
            "archived": self.archived,
            "private": self.private,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "html_url": self.html_url,
            "default_branch": self.default_branch,
            "avatar_url": self.avatar_url,
            "starred_at": self.starred_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Repository":
        """Constructs an instance from a dictionary."""
        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            owner=data.get("owner", ""),
            description=data.get("description", ""),
            language=data.get("language", "None"),
            topics=data.get("topics", []),
            fork=data.get("fork", False),
            archived=data.get("archived", False),
            private=data.get("private", False),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            html_url=data.get("html_url", ""),
            default_branch=data.get("default_branch", ""),
            avatar_url=data.get("avatar_url", ""),
            starred_at=data.get("starred_at")
        )
