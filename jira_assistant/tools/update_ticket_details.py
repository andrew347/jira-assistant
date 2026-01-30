from typing import Any

import httpx
from mcp.types import Tool, TextContent

from ..config import JIRA_HOST, SPRINT_FIELD, get_auth_header
from .transition_ticket import transition_ticket


tool = Tool(
    name="update_ticket_details",
    description="Update fields on an existing Jira ticket. Only provided fields will be updated. Can also transition the ticket to a new status.",
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
            "status": {
                "type": "string",
                "description": "Transition to a new status (e.g., 'In Progress', 'Done', 'To Do')",
            },
            "assignee": {
                "type": "string",
                "description": "Assignee: use 'me' for self-assignment, 'unassigned' to remove assignee, or a Jira account ID.",
            },
            "priority": {
                "type": "string",
                "description": "Priority (e.g., 'Highest', 'High', 'Medium', 'Low', 'Lowest')",
            },
            "labels": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Labels to set on the ticket (e.g., ['backend', 'urgent']). Replaces existing labels.",
            },
            "sprint": {
                "type": "integer",
                "description": "Sprint ID (numeric) to move the ticket to",
            },
            "epic_key": {
                "type": "string",
                "description": "Epic key to link this ticket to (e.g., 'PROJ-100')",
            },
        },
        "required": ["ticket_key"],
    },
)


async def update_ticket(
    ticket_key: str,
    summary: str | None = None,
    description: str | None = None,
    status: str | None = None,
    assignee: str | None = None,
    priority: str | None = None,
    labels: list[str] | None = None,
    sprint: int | None = None,
    epic_key: str | None = None,
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
    
    if assignee is not None:
        if assignee.lower() == "unassigned" or assignee == "":
            fields["assignee"] = None
        elif assignee.lower() == "me":
            # Get current user's account ID
            async with httpx.AsyncClient() as client:
                me_response = await client.get(
                    f"{JIRA_HOST}/rest/api/3/myself",
                    headers={
                        "Authorization": get_auth_header(),
                        "Accept": "application/json",
                    },
                )
                if me_response.is_success:
                    me_data = me_response.json()
                    fields["assignee"] = {"accountId": me_data.get("accountId")}
                else:
                    raise Exception("Failed to get current user info for self-assignment")
        else:
            # Jira Cloud requires accountId for assignment
            fields["assignee"] = {"accountId": assignee}
    
    if priority:
        fields["priority"] = {"name": priority}
    
    if labels is not None:
        fields["labels"] = labels
    
    if sprint:
        fields[SPRINT_FIELD] = sprint
    
    if epic_key:
        fields["parent"] = {"key": epic_key}
    
    # Update fields if any provided
    if fields:
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
    
    # Transition if status provided
    new_status = None
    if status:
        transition_result = await transition_ticket(ticket_key, status)
        new_status = transition_result.get("new_status")
    
    if not fields and not status:
        raise Exception("No fields to update and no status transition requested")
    
    return {
        "key": ticket_key,
        "updated": bool(fields),
        "transitioned": bool(status),
        "new_status": new_status,
        "url": f"{JIRA_HOST}/browse/{ticket_key}",
    }


async def handler(arguments: dict[str, Any]) -> list[TextContent]:
    ticket_key = arguments.get("ticket_key")
    if not ticket_key:
        return [TextContent(type="text", text="Error: ticket_key is required")]
    
    result = await update_ticket(
        ticket_key=ticket_key,
        summary=arguments.get("summary"),
        description=arguments.get("description"),
        status=arguments.get("status"),
        assignee=arguments.get("assignee"),
        priority=arguments.get("priority"),
        labels=arguments.get("labels"),
        sprint=arguments.get("sprint"),
        epic_key=arguments.get("epic_key"),
    )
    
    output = f"Updated ticket: {result['key']}"
    if result.get("transitioned") and result.get("new_status"):
        output += f"\nStatus: {result['new_status']}"
    output += f"\nURL: {result['url']}"
    
    return [TextContent(type="text", text=output)]
