from typing import Any

import httpx
from mcp.types import Tool, TextContent

from ..config import JIRA_HOST, DEFAULT_PRIORITY, DEFAULT_ISSUE_TYPE, SPRINT_FIELD, get_auth_header, get_default_sprint_id, get_default_project
from .search_similar_tickets import search_similar_tickets


tool = Tool(
    name="create_new_ticket",
    description=f"Create a new Jira ticket using default settings (priority: {DEFAULT_PRIORITY}, type: {DEFAULT_ISSUE_TYPE}). Uses current default project and sprint from config (set via update_config). IMPORTANT: Before calling this tool, ALWAYS use search_similar_tickets first to check for duplicates or related existing work. Ticket descriptions MUST include: (1) A 1-2 sentence introduction explaining the context/problem, and (2) Bulleted success criteria defining what 'done' looks like.",
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
    # If epic_key is provided, extract project from it (e.g., "PROJ2-100" -> "PROJ2")
    if epic_key:
        project_key = epic_key.rsplit("-", 1)[0]
    else:
        project_key = get_default_project()
        if not project_key:
            raise Exception("No default project configured. Set PROJECT_KEYS in .env or use update_config.")
    
    fields: dict[str, Any] = {
        "project": {"key": project_key},
        "summary": summary,
        "issuetype": {"name": DEFAULT_ISSUE_TYPE},
        "priority": {"name": DEFAULT_PRIORITY},
    }
    
    sprint_id = get_default_sprint_id()
    if sprint_id:
        fields[SPRINT_FIELD] = int(sprint_id)
    
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
    
    default_project = get_default_project()
    if not default_project:
        return [TextContent(type="text", text="Error: No default project configured. Set PROJECT_KEYS in .env or use update_config.")]
    
    similar = await search_similar_tickets(summary, max_results=5)
    
    warning = ""
    if similar:
        warning = f"⚠️ WARNING: Found {len(similar)} potentially similar ticket(s):\n"
        for t in similar[:3]:
            warning += f"  • [{t['key']}] {t['summary']} ({t['status']})\n"
        warning += "\nProceeding with ticket creation...\n\n"
    
    epic_key = arguments.get("epic_key")
    result = await create_ticket(
        summary=summary,
        description=arguments.get("description"),
        epic_key=epic_key,
    )
    
    # Show actual project used (inferred from epic or default)
    project_used = epic_key.rsplit("-", 1)[0] if epic_key else default_project
    return [TextContent(type="text", text=f"{warning}Created ticket: {result['key']}\nProject: {project_used} | Type: {DEFAULT_ISSUE_TYPE} | Priority: {DEFAULT_PRIORITY}\nURL: {result['url']}")]
