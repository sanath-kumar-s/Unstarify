import time
import requests
from typing import List, Dict, Any, Callable, Optional, Tuple
from models import Repository

class GitHubAPIError(Exception):
    """Base exception for GitHub API errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body

class RateLimitExceededError(GitHubAPIError):
    """Exception raised when GitHub API rate limit is exceeded."""
    def __init__(self, reset_time: float, message: str = "Rate limit exceeded"):
        super().__init__(message)
        self.reset_time = reset_time

class GitHubAPI:
    BASE_URL = "https://api.github.com"

    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.star+json",  # Fetch starred_at info
            "X-GitHub-Api-Version": "2022-11-28"
        }

    def _handle_rate_limit(self, headers: Dict[str, str]) -> None:
        """Checks rate limit headers and raises RateLimitExceededError if remaining limit is 0."""
        remaining = headers.get("X-RateLimit-Remaining")
        reset = headers.get("X-RateLimit-Reset")
        
        if remaining is not None and int(remaining) <= 0:
            if reset is not None:
                reset_epoch = float(reset)
                raise RateLimitExceededError(reset_epoch, f"Rate limit reached. Reset at {reset_epoch}")

    def _request_with_retry(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None, 
        log_callback: Optional[Callable[[str], None]] = None
    ) -> requests.Response:
        """Executes a request with a retry mechanism (up to 3 attempts) and handles rate limits."""
        url = f"{self.BASE_URL}{endpoint}" if endpoint.startswith("/") else endpoint
        attempts = 3
        
        for attempt in range(1, attempts + 1):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    params=params,
                    timeout=15
                )
                
                # Check rate limiting
                self._handle_rate_limit(response.headers)
                
                # Handle status codes
                if response.status_code == 403:
                    # Could be secondary/abuse rate limit
                    body = response.json() if response.text else {}
                    message = body.get("message", "")
                    if "abuse" in message.lower() or "secondary" in message.lower() or "rate limit" in message.lower():
                        retry_after = response.headers.get("Retry-After")
                        wait_sec = int(retry_after) if retry_after else 60
                        if log_callback:
                            log_callback(f"Secondary rate limit triggered. Pausing for {wait_sec}s...")
                        time.sleep(wait_sec)
                        continue
                
                return response
                
            except RateLimitExceededError as e:
                # Primary rate limit reached
                reset_duration = max(1.0, e.reset_time - time.time())
                if log_callback:
                    log_callback(f"Rate limit exceeded. Waiting {int(reset_duration)}s for reset...")
                time.sleep(reset_duration)
                # Retry after waiting
                continue
                
            except (requests.RequestException, Exception) as e:
                if attempt == attempts:
                    raise GitHubAPIError(f"Network error: {str(e)}", status_code=None)
                
                wait_time = attempt * 2
                if log_callback:
                    log_callback(f"Network issue: {str(e)}. Retrying in {wait_time}s (Attempt {attempt}/{attempts})...")
                time.sleep(wait_time)
                
        raise GitHubAPIError("Request failed after maximum retries.")

    def validate_token(self) -> str:
        """Validates the token. Returns username if successful, raises GitHubAPIError otherwise."""
        try:
            response = self._request_with_retry("GET", "/user")
            if response.status_code == 200:
                data = response.json()
                return data.get("login", "Unknown User")
            elif response.status_code == 401:
                raise GitHubAPIError("Invalid Token (Unauthorized)", status_code=401)
            else:
                raise GitHubAPIError(f"Validation failed (HTTP {response.status_code})", status_code=response.status_code)
        except GitHubAPIError:
            raise
        except Exception as e:
            raise GitHubAPIError(f"Unexpected error: {str(e)}")

    def fetch_starred_repos(
        self, 
        page_callback: Optional[Callable[[int, int], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None
    ) -> List[Repository]:
        """Fetches all starred repositories with pagination, calling callbacks to report progress."""
        repos: List[Repository] = []
        page = 1
        per_page = 100
        
        while True:
            if log_callback:
                log_callback(f"Fetching starred repositories page {page}...")
            
            response = self._request_with_retry(
                "GET", 
                "/user/starred", 
                params={"per_page": per_page, "page": page},
                log_callback=log_callback
            )
            
            if response.status_code != 200:
                raise GitHubAPIError(f"Failed to fetch stars: HTTP {response.status_code}", response.status_code)
            
            page_data = response.json()
            if not isinstance(page_data, list):
                raise GitHubAPIError("Unexpected JSON format from GitHub API (expected array).")
                
            if not page_data:
                break
                
            for item in page_data:
                repos.append(Repository.from_api_json(item))
                
            if page_callback:
                page_callback(page, len(repos))
                
            # If we received less than per_page, we are done
            if len(page_data) < per_page:
                break
                
            page += 1
            
        return repos

    def unstar_repo(self, owner: str, repo: str, log_callback: Optional[Callable[[str], None]] = None) -> bool:
        """Removes star from a repository. Returns True if successfully unstarred (204)."""
        response = self._request_with_retry(
            "DELETE", 
            f"/user/starred/{owner}/{repo}", 
            log_callback=log_callback
        )
        if response.status_code == 204:
            return True
        else:
            raise GitHubAPIError(f"Failed to unstar {owner}/{repo}: HTTP {response.status_code}", response.status_code)

    def star_repo(self, owner: str, repo: str, log_callback: Optional[Callable[[str], None]] = None) -> bool:
        """Stars a repository. Returns True if successfully starred (204)."""
        # GitHub PUT for starring requires Content-Length: 0 if no body, requests handles this.
        response = self._request_with_retry(
            "PUT", 
            f"/user/starred/{owner}/{repo}", 
            log_callback=log_callback
        )
        if response.status_code == 204:
            return True
        else:
            raise GitHubAPIError(f"Failed to star {owner}/{repo}: HTTP {response.status_code}", response.status_code)

