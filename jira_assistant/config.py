import json
import os
from base64 import b64encode
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

JIRA_HOST = os.getenv("JIRA_HOST", "").rstrip("/")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
ACTIONABLE_STATUS = os.getenv("ACTIONABLE_STATUS", "To Do")
PROJECT_KEYS = [k.strip() for k in os.getenv("PROJECT_KEYS", "").split(",") if k.strip()]
DEFAULT_PRIORITY = os.getenv("DEFAULT_PRIORITY", "Medium")
DEFAULT_ISSUE_TYPE = os.getenv("DEFAULT_ISSUE_TYPE", "Task")
SPRINT_FIELD = "customfield_10020"  # Sprint custom field (common default)

# Path to persistent config file (stored alongside .env)
_CONFIG_FILE = Path(__file__).parent.parent / "config.json"

# In-memory config state (loaded from config.json)
_runtime_config: dict = {
    "default_sprint_id": "",
    "default_project": PROJECT_KEYS[0] if PROJECT_KEYS else "",
}


def _load_config() -> None:
    """Load config.json and override in-memory config if it exists."""
    global _runtime_config
    if _CONFIG_FILE.exists():
        try:
            with open(_CONFIG_FILE, "r") as f:
                saved = json.load(f)
                _runtime_config.update(saved)
        except (json.JSONDecodeError, IOError):
            pass  # Use defaults if file is corrupted


def _save_config() -> None:
    """Persist current runtime config to config.json."""
    with open(_CONFIG_FILE, "w") as f:
        json.dump(_runtime_config, f, indent=2)


# Load config on module import
_load_config()


def get_default_sprint_id() -> str:
    """Get the current default sprint ID."""
    return str(_runtime_config.get("default_sprint_id", ""))


def set_default_sprint_id(sprint_id: str | int) -> None:
    """Update the default sprint ID and persist to config.json."""
    _runtime_config["default_sprint_id"] = str(sprint_id) if sprint_id else ""
    _save_config()


def get_default_project() -> str:
    """Get the current default project key."""
    return _runtime_config.get("default_project", "")


def set_default_project(project_key: str) -> None:
    """Update the default project and persist to config.json."""
    _runtime_config["default_project"] = project_key
    _save_config()


def get_auth_header() -> str:
    credentials = f"{JIRA_EMAIL}:{JIRA_API_TOKEN}"
    encoded = b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


def get_project_jql() -> str:
    if PROJECT_KEYS:
        return f'project IN ({", ".join(PROJECT_KEYS)})'
    return ""
