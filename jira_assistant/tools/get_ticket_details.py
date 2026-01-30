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
        # Fetch ticket details
        response = await client.get(
            f"{JIRA_HOST}/rest/api/2/issue/{ticket_key}",
            params={
                "fields": "*all",
                "expand": "names",
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
        
        # Fetch available transitions
        transitions_response = await client.get(
            f"{JIRA_HOST}/rest/api/3/issue/{ticket_key}/transitions",
            headers={
                "Authorization": get_auth_header(),
                "Accept": "application/json",
            },
        )
        available_transitions = []
        if transitions_response.is_success:
            transitions_data = transitions_response.json()
            available_transitions = [t.get("name") for t in transitions_data.get("transitions", [])]
    
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
    
    # Parse sprint info - find sprint field dynamically
    # Sprint fields are typically custom fields with sprint data (list of objects with name, state, etc.)
    sprint = None
    field_names = issue.get("names", {})
    for field_id, field_name in field_names.items():
        if "sprint" in field_name.lower():
            sprint_data = fields.get(field_id)
            if sprint_data:
                if isinstance(sprint_data, list) and sprint_data:
                    # Get the most recent/active sprint
                    for s in sprint_data:
                        if isinstance(s, dict):
                            # Prefer active sprint
                            if s.get("state") == "active":
                                sprint = s.get("name")
                                break
                            elif not sprint:
                                sprint = s.get("name")
                        else:
                            sprint = str(s)
                elif isinstance(sprint_data, dict):
                    sprint = sprint_data.get("name")
            break
    
    # Parse parent (epic)
    parent = fields.get("parent")
    epic_key = parent.get("key") if parent else None
    epic_summary = parent.get("fields", {}).get("summary") if parent else None
    
    # Parse labels
    labels = fields.get("labels", [])
    
    return {
        "key": issue.get("key"),
        "summary": fields.get("summary"),
        "status": fields.get("status", {}).get("name"),
        "available_transitions": available_transitions,
        "priority": fields.get("priority", {}).get("name"),
        "project": fields.get("project", {}).get("name"),
        "type": fields.get("issuetype", {}).get("name"),
        "sprint": sprint,
        "epic_key": epic_key,
        "epic_summary": epic_summary,
        "labels": labels,
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
    
    transitions = ", ".join(ticket['available_transitions']) if ticket['available_transitions'] else "None"
    labels = ", ".join(ticket['labels']) if ticket['labels'] else "None"
    epic = f"{ticket['epic_key']} ({ticket['epic_summary']})" if ticket['epic_key'] else "None"
    
    result = f"""Ticket: {ticket['key']}
Summary: {ticket['summary']}
Status: {ticket['status']}
Available transitions: {transitions}
Priority: {ticket['priority']}
Project: {ticket['project']}
Type: {ticket['type']}
Sprint: {ticket['sprint'] or 'None'}
Epic: {epic}
Labels: {labels}
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
