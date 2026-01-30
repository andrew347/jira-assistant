from typing import Any

import httpx
from mcp.types import Tool, TextContent

from ..config import JIRA_HOST, get_auth_header
from .search_similar_tickets import search_similar_tickets


tool = Tool(
    name="create_new_epic",
    description="Create a new Jira epic. Automatically checks for similar existing epics before creation and warns if potential duplicates are found.",
    inputSchema={
        "type": "object",
        "properties": {
            "project": {
                "type": "string",
                "description": "Project key (e.g., 'PROJ')",
            },
            "summary": {
                "type": "string",
                "description": "Epic title/summary",
            },
            "description": {
                "type": "string",
                "description": "Detailed description of the epic",
            },
        },
        "required": ["project", "summary"],
    },
)


async def create_epic(
    project: str,
    summary: str,
    description: str | None = None,
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "project": {"key": project},
        "summary": summary,
        "issuetype": {"name": "Epic"},
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
    project = arguments.get("project")
    summary = arguments.get("summary")
    if not project or not summary:
        return [TextContent(type="text", text="Error: project and summary are required")]
    
    similar = await search_similar_tickets(f"{summary} Epic", max_results=5)
    
    warning = ""
    if similar:
        warning = f"⚠️ WARNING: Found {len(similar)} potentially similar ticket(s):\n"
        for t in similar[:3]:
            warning += f"  • [{t['key']}] {t['summary']} ({t['status']})\n"
        warning += "\nProceeding with epic creation...\n\n"
    
    result = await create_epic(
        project=project,
        summary=summary,
        description=arguments.get("description"),
    )
    
    return [TextContent(type="text", text=f"{warning}Created epic: {result['key']}\nURL: {result['url']}")]
