from typing import Any

import httpx
from mcp.types import Tool, TextContent

from ..config import JIRA_HOST, get_auth_header


tool = Tool(
    name="get_ticket_details",
    description="Get detailed information about a specific Jira ticket including description and comments.",
    inputSchema={
        "type": "object",
        "properties": {
            "ticket_key": {
                "type": "string",
                "description": "The Jira ticket key (e.g., 'PROJ-123')",
            },
        },
        "required": ["ticket_key"],
    },
)


async def fetch_ticket_details(ticket_key: str) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{JIRA_HOST}/rest/api/2/issue/{ticket_key}",
            params={
                "fields": "summary,status,priority,created,updated,project,issuetype,description,comment,assignee,reporter",
            },
            headers={
                "Authorization": get_auth_header(),
                "Accept": "application/json",
            },
        )
        if not response.is_success:
            error_detail = response.text
            raise Exception(f"Jira API error {response.status_code}: {error_detail}")
        issue = response.json()
    
    fields = issue.get("fields", {})
    description = fields.get("description")
    if isinstance(description, dict) and description.get("content"):
        desc_text = ""
        for block in description["content"]:
            if block.get("type") == "paragraph":
                for item in block.get("content", []):
                    if item.get("type") == "text":
                        desc_text += item.get("text", "")
                desc_text += "\n"
    else:
        desc_text = description or ""
    
    comments = []
    for comment in fields.get("comment", {}).get("comments", []):
        body = comment.get("body", "")
        if isinstance(body, dict) and body.get("content"):
            comment_body = ""
            for block in body["content"]:
                if block.get("type") == "paragraph":
                    for item in block.get("content", []):
                        if item.get("type") == "text":
                            comment_body += item.get("text", "")
        else:
            comment_body = body if isinstance(body, str) else ""
        comments.append({
            "author": comment.get("author", {}).get("displayName"),
            "created": comment.get("created"),
            "body": comment_body,
        })
    
    return {
        "key": issue.get("key"),
        "summary": fields.get("summary"),
        "status": fields.get("status", {}).get("name"),
        "priority": fields.get("priority", {}).get("name"),
        "project": fields.get("project", {}).get("name"),
        "type": fields.get("issuetype", {}).get("name"),
        "assignee": fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
        "reporter": fields.get("reporter", {}).get("displayName") if fields.get("reporter") else None,
        "created": fields.get("created"),
        "updated": fields.get("updated"),
        "description": desc_text.strip(),
        "comments": comments,
        "url": f"{JIRA_HOST}/browse/{issue.get('key')}",
    }


async def handler(arguments: dict[str, Any]) -> list[TextContent]:
    ticket_key = arguments.get("ticket_key")
    if not ticket_key:
        return [TextContent(type="text", text="Error: ticket_key is required")]
    
    ticket = await fetch_ticket_details(ticket_key)
    
    result = f"""Ticket: {ticket['key']}
Summary: {ticket['summary']}
Status: {ticket['status']}
Priority: {ticket['priority']}
Project: {ticket['project']}
Type: {ticket['type']}
Assignee: {ticket['assignee'] or 'Unassigned'}
Reporter: {ticket['reporter'] or 'Unknown'}
Created: {ticket['created']}
Updated: {ticket['updated']}
URL: {ticket['url']}

Description:
{ticket['description'] or 'No description'}
"""
    
    if ticket['comments']:
        result += f"\nComments ({len(ticket['comments'])}):\n"
        for comment in ticket['comments'][-5:]:
            result += f"\n--- {comment['author']} ({comment['created']}) ---\n{comment['body']}\n"
    
    return [TextContent(type="text", text=result)]
