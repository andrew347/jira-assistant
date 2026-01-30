from typing import Any

import httpx
from mcp.types import Tool, TextContent

from ..config import JIRA_HOST, DEFAULT_PROJECT, DEFAULT_PRIORITY, DEFAULT_ISSUE_TYPE, get_auth_header
from .search_similar_tickets import search_similar_tickets


tool = Tool(
    name="create_new_ticket",
    description=f"Create a new Jira ticket using default settings (project: {DEFAULT_PROJECT or 'not set'}, priority: {DEFAULT_PRIORITY}, type: {DEFAULT_ISSUE_TYPE}). Only requires a summary. For more control, use create_new_ticket_advanced.",
    inputSchema={
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Ticket title/summary",
            },
            "description": {
                "type": "string",
                "description": "Detailed description of the ticket",
            },
            "epic_key": {
                "type": "string",
                "description": "Epic key to link this ticket to (e.g., 'PROJ-100')",
            },
        },
        "required": ["summary"],
    },
)


async def create_ticket(
    summary: str,
    description: str | None = None,
    epic_key: str | None = None,
) -> dict[str, Any]:
    if not DEFAULT_PROJECT:
        raise Exception("No default project configured. Set PROJECT_KEYS in .env or use create_new_ticket_advanced.")
    
    fields: dict[str, Any] = {
        "project": {"key": DEFAULT_PROJECT},
        "summary": summary,
        "issuetype": {"name": DEFAULT_ISSUE_TYPE},
        "priority": {"name": DEFAULT_PRIORITY},
    }
    
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
    
    if epic_key:
        fields["parent"] = {"key": epic_key}
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{JIRA_HOST}/rest/api/3/issue",
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
        data = response.json()
    
    return {
        "key": data.get("key"),
        "url": f"{JIRA_HOST}/browse/{data.get('key')}",
    }


async def handler(arguments: dict[str, Any]) -> list[TextContent]:
    summary = arguments.get("summary")
    if not summary:
        return [TextContent(type="text", text="Error: summary is required")]
    
    if not DEFAULT_PROJECT:
        return [TextContent(type="text", text="Error: No default project configured. Set PROJECT_KEYS in .env or use create_new_ticket_advanced.")]
    
    similar = await search_similar_tickets(summary, max_results=5)
    
    warning = ""
    if similar:
        warning = f"⚠️ WARNING: Found {len(similar)} potentially similar ticket(s):\n"
        for t in similar[:3]:
            warning += f"  • [{t['key']}] {t['summary']} ({t['status']})\n"
        warning += "\nProceeding with ticket creation...\n\n"
    
    result = await create_ticket(
        summary=summary,
        description=arguments.get("description"),
        epic_key=arguments.get("epic_key"),
    )
    
    return [TextContent(type="text", text=f"{warning}Created ticket: {result['key']}\nProject: {DEFAULT_PROJECT} | Type: {DEFAULT_ISSUE_TYPE} | Priority: {DEFAULT_PRIORITY}\nURL: {result['url']}")]
