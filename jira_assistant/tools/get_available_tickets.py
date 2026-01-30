from typing import Any

import httpx
from mcp.types import Tool, TextContent

from ..config import JIRA_HOST, ACTIONABLE_STATUS, PROJECT_KEYS, get_auth_header, get_project_jql


tool = Tool(
    name="get_available_tickets",
    description="Get unassigned tickets that are ready to be picked up. Returns tickets in the actionable status (configured via ACTIONABLE_STATUS env var, default 'To Do').",
    inputSchema={
        "type": "object",
        "properties": {
            "max_results": {
                "type": "integer",
                "description": "Maximum number of tickets to return (default: 50)",
                "default": 50,
            },
            "status": {
                "type": "string",
                "description": "Override the actionable status filter",
            },
            "project": {
                "type": "string",
                "description": "Filter by project key (e.g., 'PROJ')",
            },
        },
    },
)


async def fetch_available_tickets(
    max_results: int = 50,
    status_override: str | None = None,
    project_override: str | None = None,
) -> list[dict[str, Any]]:
    status = status_override or ACTIONABLE_STATUS
    jql_parts = [
        "assignee IS EMPTY",
        f'status = "{status}"',
    ]
    
    if project_override:
        jql_parts.append(f'project = "{project_override}"')
    elif PROJECT_KEYS:
        jql_parts.append(get_project_jql())
    
    jql = " AND ".join(jql_parts) + " ORDER BY updated DESC"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{JIRA_HOST}/rest/api/3/search/jql",
            json={
                "jql": jql,
                "maxResults": max_results,
                "fields": ["summary", "status", "priority", "created", "updated", "project", "issuetype", "description"],
            },
            headers={
                "Authorization": get_auth_header(),
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        if not response.is_success:
            error_detail = response.text
            raise Exception(f"Jira API error {response.status_code}: {error_detail}")
        data = response.json()
    
    tickets = []
    for issue in data.get("issues", []):
        fields = issue.get("fields", {})
        tickets.append({
            "key": issue.get("key"),
            "summary": fields.get("summary"),
            "status": fields.get("status", {}).get("name"),
            "priority": fields.get("priority", {}).get("name"),
            "project": fields.get("project", {}).get("name"),
            "type": fields.get("issuetype", {}).get("name"),
            "created": fields.get("created"),
            "updated": fields.get("updated"),
            "url": f"{JIRA_HOST}/browse/{issue.get('key')}",
        })
    
    return tickets


def format_ticket_list(tickets: list[dict[str, Any]], header: str) -> str:
    if not tickets:
        return f"No {header.lower()} found."
    
    result_lines = [f"Found {len(tickets)} {header.lower()}:\n"]
    for ticket in tickets:
        result_lines.append(
            f"• [{ticket['key']}] {ticket['summary']}\n"
            f"  Status: {ticket['status']} | Priority: {ticket['priority']} | Project: {ticket['project']}\n"
            f"  Type: {ticket.get('type', 'N/A')} | Updated: {ticket.get('updated', 'N/A')}\n"
            f"  URL: {ticket['url']}\n"
        )
    return "\n".join(result_lines)


async def handler(arguments: dict[str, Any]) -> list[TextContent]:
    tickets = await fetch_available_tickets(
        max_results=arguments.get("max_results", 50),
        status_override=arguments.get("status"),
        project_override=arguments.get("project"),
    )
    return [TextContent(type="text", text=format_ticket_list(tickets, "available ticket(s)"))]
