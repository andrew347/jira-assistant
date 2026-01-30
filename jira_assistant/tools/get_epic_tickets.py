from typing import Any

import httpx
from mcp.types import Tool, TextContent

from ..config import JIRA_HOST, get_auth_header


tool = Tool(
    name="get_epic_tickets",
    description="Get all tickets/stories that belong to a specific epic.",
    inputSchema={
        "type": "object",
        "properties": {
            "epic_key": {
                "type": "string",
                "description": "The epic key (e.g., 'PROJ-100')",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of tickets to return (default: 50)",
                "default": 50,
            },
            "include_done": {
                "type": "boolean",
                "description": "Include completed tickets (default: true)",
                "default": True,
            },
        },
        "required": ["epic_key"],
    },
)


async def fetch_epic_tickets(
    epic_key: str,
    max_results: int = 50,
    include_done: bool = True,
) -> list[dict[str, Any]]:
    jql_parts = [f'parent = "{epic_key}"']
    
    if not include_done:
        jql_parts.append('statusCategory != "Done"')
    
    jql = " AND ".join(jql_parts) + " ORDER BY status ASC, updated DESC"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{JIRA_HOST}/rest/api/3/search/jql",
            json={
                "jql": jql,
                "maxResults": max_results,
                "fields": ["summary", "status", "priority", "assignee", "issuetype", "updated"],
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
            "type": fields.get("issuetype", {}).get("name"),
            "assignee": fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
            "updated": fields.get("updated"),
            "url": f"{JIRA_HOST}/browse/{issue.get('key')}",
        })
    
    return tickets


async def handler(arguments: dict[str, Any]) -> list[TextContent]:
    epic_key = arguments.get("epic_key")
    if not epic_key:
        return [TextContent(type="text", text="Error: epic_key is required")]
    
    tickets = await fetch_epic_tickets(
        epic_key=epic_key,
        max_results=arguments.get("max_results", 50),
        include_done=arguments.get("include_done", True),
    )
    
    if not tickets:
        return [TextContent(type="text", text=f"No tickets found under epic {epic_key}")]
    
    # Group by status
    by_status: dict[str, list] = {}
    for ticket in tickets:
        status = ticket["status"]
        if status not in by_status:
            by_status[status] = []
        by_status[status].append(ticket)
    
    result_lines = [f"Found {len(tickets)} ticket(s) under epic {epic_key}:\n"]
    
    for status, status_tickets in by_status.items():
        result_lines.append(f"\n### {status} ({len(status_tickets)})")
        for ticket in status_tickets:
            assignee = ticket['assignee'] or 'Unassigned'
            result_lines.append(
                f"• [{ticket['key']}] {ticket['summary']}\n"
                f"  Type: {ticket['type']} | Priority: {ticket['priority']} | Assignee: {assignee}\n"
                f"  URL: {ticket['url']}"
            )
    
    return [TextContent(type="text", text="\n".join(result_lines))]
