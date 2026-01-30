import os
from base64 import b64encode

from dotenv import load_dotenv

load_dotenv()

JIRA_HOST = os.getenv("JIRA_HOST", "").rstrip("/")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
ACTIONABLE_STATUS = os.getenv("ACTIONABLE_STATUS", "To Do")
PROJECT_KEYS = [k.strip() for k in os.getenv("PROJECT_KEYS", "").split(",") if k.strip()]
DEFAULT_PROJECT = PROJECT_KEYS[0] if PROJECT_KEYS else ""
DEFAULT_PRIORITY = os.getenv("DEFAULT_PRIORITY", "Medium")
DEFAULT_ISSUE_TYPE = os.getenv("DEFAULT_ISSUE_TYPE", "Task")
DEFAULT_SPRINT_ID = os.getenv("DEFAULT_SPRINT_ID", "")  # Sprint ID (numeric)
SPRINT_FIELD = "customfield_10020"  # Sprint custom field (common default)


def get_auth_header() -> str:
    credentials = f"{JIRA_EMAIL}:{JIRA_API_TOKEN}"
    encoded = b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


def get_project_jql() -> str:
    if PROJECT_KEYS:
        return f'project IN ({", ".join(PROJECT_KEYS)})'
    return ""
