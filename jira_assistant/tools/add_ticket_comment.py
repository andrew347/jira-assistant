from typing import Any

import httpx
from mcp.types import Tool, TextContent

from ..config import JIRA_HOST, get_auth_header


tool = Tool(
    name="add_ticket_comment",
    description="Add a comment to a Jira ticket.",
    inputSchema={
        "type": "object",
        "properties": {
            "ticket_key": {
                "type": "string",
                "description": "The Jira ticket key (e.g., 'PROJ-123')",
            },
            "comment": {
                "type": "string",
                "description": "The comment text to add",
            },
        },
        "required": ["ticket_key", "comment"],
    },
)


async def add_comment(
    ticket_key: str,
    comment: str,
) -> dict[str, Any]:
    body = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": comment}]
                }
            ]
        }
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{JIRA_HOST}/rest/api/3/issue/{ticket_key}/comment",
            json=body,
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
    
    return {
        "ticket_key": ticket_key,
        "comment_id": data.get("id"),
        "url": f"{JIRA_HOST}/browse/{ticket_key}",
    }


async def handler(arguments: dict[str, Any]) -> list[TextContent]:
    ticket_key = arguments.get("ticket_key")
    comment = arguments.get("comment")
    
    if not ticket_key:
        return [TextContent(type="text", text="Error: ticket_key is required")]
    if not comment:
        return [TextContent(type="text", text="Error: comment is required")]
    
    result = await add_comment(ticket_key, comment)
    
    return [TextContent(type="text", text=f"Added comment to {result['ticket_key']}\nURL: {result['url']}")]
