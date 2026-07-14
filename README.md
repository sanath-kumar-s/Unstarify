# GitHub Stars Manager & Remover

A modern dark-themed desktop application built in Python using PySide6 (Qt6) that connects to the GitHub REST API to bulk manage, export, import, and remove repository stars from your personal account.

---

## Features

- **Modern Dark Theme UI**: Built with PySide6 (Qt6) using a custom dark QSS stylesheet.
- **Asynchronous Design**: Background workers run via `QThread` and communicate with `Signals` and `Slots` to ensure the interface never freezes or stutters, even with 5000+ stars.
- **Secure Token Connection**: Connect with a GitHub Personal Access Token (PAT) with optional saving locally.
- **Live Search & Filter**: Instantaneous search by name, owner, description, or topics. Filters by Language, Archived, and Fork status.
- **Sorting Options**: Sort by Repository Name, Owner, Language, or Last Updated.
- **Interactive Repository Grid**:
  - Native checkboxes (`☑` / `☐`) to select items for batch operations.
  - Multi-select actions: Select All, Deselect All, and Invert Selection.
  - Right-click context menu (Open Repository, Copy URL, Open Owner Profile).
  - Double-click to open any repository directly in your web browser.
- **Interactive Progress Bar**: Live estimated completion times, real-time counters, and cancellation controls.
- **Console Log Output**: Timestamped operation logs displayed inside a clean scrolling code font window.
- **Export / Import Utilities**:
  - Export starred repositories to CSV or JSON formats.
  - Import JSON list backups to compare with your current account status and re-star missing ones automatically.
- **Data Cleanup Script**: Clean settings, credentials, and cache folders with one click.

---

## Installation & Setup

### Prerequisites
- Python 3.11 or higher
- A GitHub Personal Access Token (PAT) with `public_repo` (for public repos) or `repo` (for private repos) scope.

### Dependencies
Install the required dependencies using pip:
```bash
pip install PySide6 requests python-dotenv
```

### Running the App
Start the application by running:
```bash
python main.py
```

### Resetting Configurations
To wipe all saved tokens, local configurations (`config.json`), and system caches, run:
```bash
python clear_data.py
```

---

## API Usage & Data Details

The application communicates exclusively with the official GitHub REST API. **No browser automation or Selenium is used.**

### API Actions Done
1. **Token Validation**:
   - **Endpoint**: `GET https://api.github.com/user`
   - **Header**: `Authorization: Bearer <TOKEN>`
   - **Purpose**: Authenticates the token and fetches the logged-in username.
2. **Fetch Starred Repositories**:
   - **Endpoint**: `GET https://api.github.com/user/starred`
   - **Parameters**: `per_page=100`, `page=<n>`
   - **Accept Header**: `application/vnd.github.star+json` (used specifically to pull the `starred_at` timestamp).
   - **Purpose**: Loops sequentially over all pages of your starred list until everything is downloaded.
3. **Unstar a Repository**:
   - **Endpoint**: `DELETE https://api.github.com/user/starred/{owner}/{repo}`
   - **Purpose**: Removes the star from the specified repository.
4. **Star a Repository** (Re-star imported missing ones):
   - **Endpoint**: `PUT https://api.github.com/user/starred/{owner}/{repo}`
   - **Purpose**: Re-adds a star to the specified repository.

### Rate Limit & Error Management
- **Primary Rate Limits**: Monitors `X-RateLimit-Remaining` and `X-RateLimit-Reset` headers. If the remaining quota drops to `0`, the app automatically pauses operations and calculates the exact duration to sleep before resumes.
- **Secondary / Abuse Limits**: Handles HTTP `403` rate limits by extracting the `Retry-After` header and waiting for the specified seconds.
- **Retry Mechanism**: Transient network issues are automatically retried up to 3 times before skipping, logging details directly to the console.

---

## Data Scheme (Fields Pulled)

Each starred repository entry stores:
* **id**: Unique Repository ID (integer)
* **name**: Repository name
* **owner**: Owner's GitHub login username
* **description**: Repository description (if any)
* **language**: Main coding language (e.g. Python, Rust)
* **topics**: List of keywords/tags associated with the repo
* **fork**: Boolean indicating whether it is a fork
* **archived**: Boolean indicating whether the project is archived
* **private**: Boolean indicating if the repo is private/public
* **created_at**: Creation timestamp
* **updated_at**: Last update timestamp
* **html_url**: Repository web link
* **default_branch**: The primary branch name (e.g. `main`)
* **avatar_url**: Profile icon URL of the repository owner
* **starred_at**: The timestamp of when you starred it

---

## Code Base Organization

- `main.py`: Entry point that initiates the Qt application window.
- `gui.py`: Manages the PySide6 views, stylesheet (QSS), right-click interactions, and launches background thread workers to avoid main event loop blockage.
- `api.py`: Integrates with the GitHub REST API, handling page requests, retries, and rate throttling.
- `models.py`: Defines the `Repository` dataclass representation.
- `utils.py`: Contains utility functions to read/write JSON & CSV files and compares differences between local files and live profiles.
- `config.py`: Loads and saves local preferences (`config.json`), keeping window sizes, user preferences, and token details.
- `clear_data.py`: A convenience script that resets config settings and wipes stored secrets.
