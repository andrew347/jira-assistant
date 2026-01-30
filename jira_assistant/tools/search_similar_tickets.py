from typing import Any

import httpx
from mcp.types import Tool, TextContent

from ..config import JIRA_HOST, PROJECT_KEYS, get_auth_header, get_project_jql


tool = Tool(
    name="search_similar_tickets",
    description="Search for tickets with similar text to find potential duplicates or related work. Uses Jira's text search for fuzzy keyword matching.",
    inputSchema={
        "type": "object",
        "properties": {
            "search_text": {
                "type": "string",
                "description": "Text to search for in ticket summaries and descriptions",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results (default: 10)",
                "default": 10,
            },
            "include_done": {
                "type": "boolean",
                "description": "Include completed tickets in search (default: false)",
                "default": False,
            },
            "project": {
                "type": "string",
                "description": "Filter by project key for faster searches (e.g., 'PROJ')",
            },
        },
        "required": ["search_text"],
    },
)


async def search_similar_tickets(
    search_text: str,
    max_results: int = 10,
    include_done: bool = False,
    project_filter: str | None = None,
) -> list[dict[str, Any]]:
    jql_parts = [f'text ~ "{search_text}"']
    
    if not include_done:
        jql_parts.append('statusCategory != "Done"')
    if project_filter:
        jql_parts.append(f'project = "{project_filter}"')
    elif PROJECT_KEYS:
        jql_parts.append(get_project_jql())
    
    jql = " AND ".join(jql_parts) + " ORDER BY updated DESC"
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{JIRA_HOST}/rest/api/3/search/jql",
            json={
                "jql": jql,
                "maxResults": max_results,
                "fields": ["summary", "status", "priority", "project", "issuetype", "assignee", "description"],
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
        description = fields.get("description")
        if isinstance(description, dict) and description.get("content"):
            desc_text = ""
            for block in description["content"]:
                if block.get("type") == "paragraph":
                    for item in block.get("content", []):
                        if item.get("type") == "text":
                            desc_text += item.get("text", "")
        else:
            desc_text = description or ""
        
        tickets.append({
            "key": issue.get("key"),
            "summary": fields.get("summary"),
            "status": fields.get("status", {}).get("name"),
            "priority": fields.get("priority", {}).get("name"),
            "project": fields.get("project", {}).get("name"),
            "type": fields.get("issuetype", {}).get("name"),
            "assignee": fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
            "description_preview": desc_text[:200] + "..." if len(desc_text) > 200 else desc_text,
            "url": f"{JIRA_HOST}/browse/{issue.get('key')}",
        })
    
    return tickets


async def handler(arguments: dict[str, Any]) -> list[TextContent]:
    search_text = arguments.get("search_text")
    if not search_text:
        return [TextContent(type="text", text="Error: search_text is required")]
    
    tickets = await search_similar_tickets(
        search_text=search_text,
        max_results=arguments.get("max_results", 10),
        include_done=arguments.get("include_done", False),
        project_filter=arguments.get("project"),
    )
    
    if not tickets:
        return [TextContent(type="text", text=f"No similar tickets found for: {search_text}")]
    
    result_lines = [f"Found {len(tickets)} potentially similar ticket(s):\n"]
    for ticket in tickets:
        result_lines.append(
            f"• [{ticket['key']}] {ticket['summary']}\n"
            f"  Status: {ticket['status']} | Assignee: {ticket['assignee'] or 'Unassigned'}\n"
            f"  Project: {ticket['project']} | Type: {ticket['type']}\n"
            f"  Preview: {ticket['description_preview']}\n"
            f"  URL: {ticket['url']}\n"
        )
    return [TextContent(type="text", text="\n".join(result_lines))]
