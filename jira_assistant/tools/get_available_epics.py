from typing import Any

import httpx
from mcp.types import Tool, TextContent

from ..config import JIRA_HOST, PROJECT_KEYS, get_auth_header, get_project_jql


tool = Tool(
    name="get_available_epics",
    description="Get open epics that can be used to link new work. Returns epics that are not yet completed.",
    inputSchema={
        "type": "object",
        "properties": {
            "max_results": {
                "type": "integer",
                "description": "Maximum number of epics to return (default: 50)",
                "default": 50,
            },
            "project": {
                "type": "string",
                "description": "Filter by project key (e.g., 'PROJ')",
            },
        },
    },
)


async def fetch_available_epics(
    max_results: int = 50,
    project_filter: str | None = None,
) -> list[dict[str, Any]]:
    jql_parts = [
        'issuetype = Epic',
        'statusCategory != "Done"',
    ]
    
    if project_filter:
        jql_parts.append(f'project = "{project_filter}"')
    elif PROJECT_KEYS:
        jql_parts.append(get_project_jql())
    
    jql = " AND ".join(jql_parts) + " ORDER BY updated DESC"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{JIRA_HOST}/rest/api/3/search/jql",
            json={
                "jql": jql,
                "maxResults": max_results,
                "fields": ["summary", "status", "priority", "project"],
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
    
    epics = []
    for issue in data.get("issues", []):
        fields = issue.get("fields", {})
        epics.append({
            "key": issue.get("key"),
            "summary": fields.get("summary"),
            "status": fields.get("status", {}).get("name"),
            "priority": fields.get("priority", {}).get("name"),
            "project": fields.get("project", {}).get("name"),
            "url": f"{JIRA_HOST}/browse/{issue.get('key')}",
        })
    
    return epics


async def handler(arguments: dict[str, Any]) -> list[TextContent]:
    epics = await fetch_available_epics(
        max_results=arguments.get("max_results", 50),
        project_filter=arguments.get("project"),
    )
    
    if not epics:
        return [TextContent(type="text", text="No open epics found.")]
    
    result_lines = [f"Found {len(epics)} open epic(s):\n"]
    for epic in epics:
        result_lines.append(
            f"• [{epic['key']}] {epic['summary']}\n"
            f"  Status: {epic['status']} | Priority: {epic['priority']} | Project: {epic['project']}\n"
            f"  URL: {epic['url']}\n"
        )
    return [TextContent(type="text", text="\n".join(result_lines))]
