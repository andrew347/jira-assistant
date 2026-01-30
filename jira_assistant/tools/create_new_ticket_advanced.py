from typing import Any

import httpx
from mcp.types import Tool, TextContent

from ..config import JIRA_HOST, DEFAULT_PROJECT, DEFAULT_PRIORITY, DEFAULT_ISSUE_TYPE, get_auth_header
from .search_similar_tickets import search_similar_tickets


tool = Tool(
    name="create_new_ticket_advanced",
    description="Create a new Jira ticket with full control over all fields. Use create_new_ticket for quick creation with defaults.",
    inputSchema={
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Ticket title/summary",
            },
            "project": {
                "type": "string",
                "description": f"Project key (e.g., 'PROJ'). Defaults to '{DEFAULT_PROJECT}' if not specified.",
            },
            "description": {
                "type": "string",
                "description": "Detailed description of the ticket",
            },
            "issue_type": {
                "type": "string",
                "description": f"Issue type (e.g., 'Task', 'Bug', 'Story'). Defaults to '{DEFAULT_ISSUE_TYPE}'.",
            },
            "priority": {
                "type": "string",
                "description": f"Priority (e.g., 'Highest', 'High', 'Medium', 'Low', 'Lowest'). Defaults to '{DEFAULT_PRIORITY}'.",
            },
            "epic_key": {
                "type": "string",
                "description": "Epic key to link this ticket to (e.g., 'PROJ-100')",
            },
            "labels": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Labels to add to the ticket (e.g., ['backend', 'urgent'])",
            },
            "assignee": {
                "type": "string",
                "description": "Assignee account ID or email",
            },
        },
        "required": ["summary"],
    },
)


async def create_ticket_advanced(
    summary: str,
    project: str | None = None,
    description: str | None = None,
    issue_type: str | None = None,
    priority: str | None = None,
    epic_key: str | None = None,
    labels: list[str] | None = None,
    assignee: str | None = None,
) -> dict[str, Any]:
    project = project or DEFAULT_PROJECT
    if not project:
        raise Exception("No project specified and no default project configured. Set PROJECT_KEYS in .env or pass project parameter.")
    
    fields: dict[str, Any] = {
        "project": {"key": project},
        "summary": summary,
        "issuetype": {"name": issue_type or DEFAULT_ISSUE_TYPE},
        "priority": {"name": priority or DEFAULT_PRIORITY},
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
    
    if labels:
        fields["labels"] = labels
    
    if assignee:
        fields["assignee"] = {"accountId": assignee} if "@" not in assignee else {"emailAddress": assignee}
    
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
        "project": project,
        "issue_type": issue_type or DEFAULT_ISSUE_TYPE,
        "priority": priority or DEFAULT_PRIORITY,
        "url": f"{JIRA_HOST}/browse/{data.get('key')}",
    }


async def handler(arguments: dict[str, Any]) -> list[TextContent]:
    summary = arguments.get("summary")
    if not summary:
        return [TextContent(type="text", text="Error: summary is required")]
    
    project = arguments.get("project") or DEFAULT_PROJECT
    if not project:
        return [TextContent(type="text", text="Error: No project specified and no default project configured. Set PROJECT_KEYS in .env or pass project parameter.")]
    
    similar = await search_similar_tickets(summary, max_results=5, project_filter=project)
    
    warning = ""
    if similar:
        warning = f"⚠️ WARNING: Found {len(similar)} potentially similar ticket(s):\n"
        for t in similar[:3]:
            warning += f"  • [{t['key']}] {t['summary']} ({t['status']})\n"
        warning += "\nProceeding with ticket creation...\n\n"
    
    result = await create_ticket_advanced(
        summary=summary,
        project=arguments.get("project"),
        description=arguments.get("description"),
        issue_type=arguments.get("issue_type"),
        priority=arguments.get("priority"),
        epic_key=arguments.get("epic_key"),
        labels=arguments.get("labels"),
        assignee=arguments.get("assignee"),
    )
    
    return [TextContent(type="text", text=f"{warning}Created ticket: {result['key']}\nProject: {result['project']} | Type: {result['issue_type']} | Priority: {result['priority']}\nURL: {result['url']}")]
