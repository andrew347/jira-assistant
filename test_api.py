"""Test script to verify Jira API connectivity."""

import asyncio
import os
from base64 import b64encode

import httpx
from dotenv import load_dotenv

load_dotenv()

JIRA_HOST = os.getenv("JIRA_HOST", "").rstrip("/")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")


def get_auth_header() -> str:
    credentials = f"{JIRA_EMAIL}:{JIRA_API_TOKEN}"
    encoded = b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


async def test_get_assigned_tickets():
    """Test fetching tickets assigned to the current user."""
    print("=" * 50)
    print("Testing: Get Assigned Tickets")
    print("=" * 50)
    print(f"Host: {JIRA_HOST}")
    print(f"Email: {JIRA_EMAIL}")
    print()

    if not all([JIRA_HOST, JIRA_EMAIL, JIRA_API_TOKEN]):
        print("ERROR: Missing required environment variables.")
        print("Make sure JIRA_HOST, JIRA_EMAIL, and JIRA_API_TOKEN are set in .env")
        return

    jql = 'assignee = currentUser() AND statusCategory != "Done" ORDER BY updated DESC'

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{JIRA_HOST}/rest/api/3/search/jql",
                json={
                    "jql": jql,
                    "maxResults": 10,
                    "fields": ["summary", "status", "priority", "project", "issuetype", "updated"],
                },
                headers={
                    "Authorization": get_auth_header(),
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )

            if not response.is_success:
                print(f"ERROR: API returned {response.status_code}")
                print(f"Response: {response.text}")
                return

            data = response.json()
            issues = data.get("issues", [])

            print(f"SUCCESS: Found {len(issues)} ticket(s) assigned to you\n")

            for issue in issues:
                fields = issue.get("fields", {})
                print(f"  [{issue.get('key')}] {fields.get('summary')}")
                print(f"    Status: {fields.get('status', {}).get('name')}")
                print(f"    Priority: {fields.get('priority', {}).get('name')}")
                print(f"    Project: {fields.get('project', {}).get('name')}")
                print(f"    URL: {JIRA_HOST}/browse/{issue.get('key')}")
                print()

    except httpx.ConnectError as e:
        print(f"ERROR: Could not connect to Jira host: {e}")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(test_get_assigned_tickets())
