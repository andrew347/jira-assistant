from typing import Any

import httpx
from mcp.types import Tool, TextContent

from ..config import JIRA_HOST, get_auth_header


tool = Tool(
    name="get_assigned_tickets",
    description="Get all Jira tickets assigned to me. By default excludes completed tickets. Optionally filter by status or project.",
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
                "description": "Filter by status (e.g., 'In Progress', 'To Do', 'Done')",
            },
            "project": {
                "type": "string",
                "description": "Filter by project key (e.g., 'PROJ')",
            },
            "exclude_done": {
                "type": "boolean",
                "description": "Exclude completed tickets (default: true)",
                "default": True,
            },
        },
    },
)


async def fetch_assigned_tickets(
    max_results: int = 50,
    status_filter: str | None = None,
    project_filter: str | None = None,
    exclude_done: bool = True,
) -> list[dict[str, Any]]:
    jql_parts = ["assignee = currentUser()"]
    
    if exclude_done:
        jql_parts.append('statusCategory != "Done"')
    if status_filter:
        jql_parts.append(f'status = "{status_filter}"')
    if project_filter:
        jql_parts.append(f'project = "{project_filter}"')
    
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
    tickets = await fetch_assigned_tickets(
        max_results=arguments.get("max_results", 50),
        status_filter=arguments.get("status"),
        project_filter=arguments.get("project"),
        exclude_done=arguments.get("exclude_done", True),
    )
    return [TextContent(type="text", text=format_ticket_list(tickets, "ticket(s) assigned to you"))]
