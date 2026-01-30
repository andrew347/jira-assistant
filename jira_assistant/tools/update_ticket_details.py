from typing import Any

import httpx
from mcp.types import Tool, TextContent

from ..config import JIRA_HOST, get_auth_header


tool = Tool(
    name="update_ticket_details",
    description="Update fields on an existing Jira ticket. Only provided fields will be updated.",
    inputSchema={
        "type": "object",
        "properties": {
            "ticket_key": {
                "type": "string",
                "description": "The Jira ticket key (e.g., 'PROJ-123')",
            },
            "summary": {
                "type": "string",
                "description": "New ticket title/summary",
            },
            "description": {
                "type": "string",
                "description": "New description",
            },
            "assignee": {
                "type": "string",
                "description": "Assignee account ID or email",
            },
        },
        "required": ["ticket_key"],
    },
)


async def update_ticket(
    ticket_key: str,
    summary: str | None = None,
    description: str | None = None,
    assignee: str | None = None,
) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    
    if summary:
        fields["summary"] = summary
    
    if description:
        fields["description"] = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": description}]
                }
            ]
        }
    
    if assignee:
        fields["assignee"] = {"accountId": assignee} if "@" not in assignee else {"emailAddress": assignee}
    
    if not fields:
        raise Exception("No fields to update")
    
    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"{JIRA_HOST}/rest/api/3/issue/{ticket_key}",
            json={"fields": fields},
            headers={
                "Authorization": get_auth_header(),
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        if not response.is_success:
            error_detail = response.text
            raise Exception(f"Jira API error {response.status_code}: {error_detail}")
    
    return {"key": ticket_key, "updated": True, "url": f"{JIRA_HOST}/browse/{ticket_key}"}


async def handler(arguments: dict[str, Any]) -> list[TextContent]:
    ticket_key = arguments.get("ticket_key")
    if not ticket_key:
        return [TextContent(type="text", text="Error: ticket_key is required")]
    
    result = await update_ticket(
        ticket_key=ticket_key,
        summary=arguments.get("summary"),
        description=arguments.get("description"),
        assignee=arguments.get("assignee"),
    )
    
    return [TextContent(type="text", text=f"Updated ticket: {result['key']}\nURL: {result['url']}")]
