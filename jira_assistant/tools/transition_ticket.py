from typing import Any

import httpx
from mcp.types import Tool, TextContent

from ..config import JIRA_HOST, get_auth_header
from .get_ticket_details import fetch_ticket_details


tool = Tool(
    name="transition_ticket",
    description="Move a ticket to a different status (e.g., 'In Progress', 'Done'). Shows available transitions if the requested one is not valid.",
    inputSchema={
        "type": "object",
        "properties": {
            "ticket_key": {
                "type": "string",
                "description": "The Jira ticket key (e.g., 'PROJ-123')",
            },
            "transition_name": {
                "type": "string",
                "description": "Name of the transition (e.g., 'In Progress', 'Done', 'To Do')",
            },
        },
        "required": ["ticket_key", "transition_name"],
    },
)


async def transition_ticket(
    ticket_key: str,
    transition_name: str,
) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{JIRA_HOST}/rest/api/3/issue/{ticket_key}/transitions",
            headers={
                "Authorization": get_auth_header(),
                "Accept": "application/json",
            },
        )
        if not response.is_success:
            error_detail = response.text
            raise Exception(f"Jira API error {response.status_code}: {error_detail}")
        transitions_data = response.json()
    
    transition_id = None
    available_transitions = []
    for t in transitions_data.get("transitions", []):
        available_transitions.append(t.get("name"))
        if t.get("name", "").lower() == transition_name.lower():
            transition_id = t.get("id")
            break
    
    if not transition_id:
        raise Exception(f"Transition '{transition_name}' not found. Available: {', '.join(available_transitions)}")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{JIRA_HOST}/rest/api/3/issue/{ticket_key}/transitions",
            json={"transition": {"id": transition_id}},
            headers={
                "Authorization": get_auth_header(),
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        if not response.is_success:
            error_detail = response.text
            raise Exception(f"Jira API error {response.status_code}: {error_detail}")
    
    ticket = await fetch_ticket_details(ticket_key)
    return {
        "key": ticket_key,
        "new_status": ticket.get("status"),
        "url": f"{JIRA_HOST}/browse/{ticket_key}",
    }


async def handler(arguments: dict[str, Any]) -> list[TextContent]:
    ticket_key = arguments.get("ticket_key")
    transition_name = arguments.get("transition_name")
    if not ticket_key or not transition_name:
        return [TextContent(type="text", text="Error: ticket_key and transition_name are required")]
    
    result = await transition_ticket(ticket_key, transition_name)
    
    return [TextContent(type="text", text=f"Transitioned {result['key']} to: {result['new_status']}\nURL: {result['url']}")]
