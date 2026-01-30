import os
import asyncio
from base64 import b64encode
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

load_dotenv()

JIRA_HOST = os.getenv("JIRA_HOST", "").rstrip("/")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
ACTIONABLE_STATUS = os.getenv("ACTIONABLE_STATUS", "To Do")
PROJECT_KEYS = [k.strip() for k in os.getenv("PROJECT_KEYS", "").split(",") if k.strip()]

server = Server("jira-assistant")


def get_auth_header() -> str:
    credentials = f"{JIRA_EMAIL}:{JIRA_API_TOKEN}"
    encoded = b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


async def fetch_assigned_tickets(
    max_results: int = 50,
    status_filter: str | None = None,
    project_filter: str | None = None,
    exclude_done: bool = True,
) -> list[dict[str, Any]]:
    jql_parts = ["assignee = currentUser()"]
    
    if exclude_done:
        jql_parts.append('statusCategory != "Done"')
    if status_filter:
        jql_parts.append(f'status = "{status_filter}"')
    if project_filter:
        jql_parts.append(f'project = "{project_filter}"')
    
    jql = " AND ".join(jql_parts) + " ORDER BY updated DESC"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{JIRA_HOST}/rest/api/3/search/jql",
            json={
                "jql": jql,
                "maxResults": max_results,
                "fields": ["summary", "status", "priority", "created", "updated", "project", "issuetype", "description"],
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
        tickets.append({
            "key": issue.get("key"),
            "summary": fields.get("summary"),
            "status": fields.get("status", {}).get("name"),
            "priority": fields.get("priority", {}).get("name"),
            "project": fields.get("project", {}).get("name"),
            "type": fields.get("issuetype", {}).get("name"),
            "created": fields.get("created"),
            "updated": fields.get("updated"),
            "url": f"{JIRA_HOST}/browse/{issue.get('key')}",
        })
    
    return tickets


def get_project_jql() -> str:
    if PROJECT_KEYS:
        return f'project IN ({", ".join(PROJECT_KEYS)})'
    return ""


async def fetch_available_tickets(
    max_results: int = 50,
    status_override: str | None = None,
    project_override: str | None = None,
) -> list[dict[str, Any]]:
    status = status_override or ACTIONABLE_STATUS
    jql_parts = [
        "assignee IS EMPTY",
        f'status = "{status}"',
    ]
    
    if project_override:
        jql_parts.append(f'project = "{project_override}"')
    elif PROJECT_KEYS:
        jql_parts.append(get_project_jql())
    
    jql = " AND ".join(jql_parts) + " ORDER BY updated DESC"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{JIRA_HOST}/rest/api/3/search/jql",
            json={
                "jql": jql,
                "maxResults": max_results,
                "fields": ["summary", "status", "priority", "created", "updated", "project", "issuetype", "description"],
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
        tickets.append({
            "key": issue.get("key"),
            "summary": fields.get("summary"),
            "status": fields.get("status", {}).get("name"),
            "priority": fields.get("priority", {}).get("name"),
            "project": fields.get("project", {}).get("name"),
            "type": fields.get("issuetype", {}).get("name"),
            "created": fields.get("created"),
            "updated": fields.get("updated"),
            "url": f"{JIRA_HOST}/browse/{issue.get('key')}",
        })
    
    return tickets


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


async def create_ticket(
    project: str,
    summary: str,
    description: str | None = None,
    issue_type: str = "Task",
    epic_key: str | None = None,
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "project": {"key": project},
        "summary": summary,
        "issuetype": {"name": issue_type},
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


async def update_ticket(
    ticket_key: str,
    summary: str | None = None,
    description: str | None = None,
    assignee: str | None = None,
) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    
    if summary:
        fields["summary"] = summary
    
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
    
    if assignee:
        fields["assignee"] = {"accountId": assignee} if "@" not in assignee else {"emailAddress": assignee}
    
    if not fields:
        raise Exception("No fields to update")
    
    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"{JIRA_HOST}/rest/api/3/issue/{ticket_key}",
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
    
    return {"key": ticket_key, "updated": True, "url": f"{JIRA_HOST}/browse/{ticket_key}"}


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


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_assigned_tickets",
            description="Get all Jira tickets assigned to me. By default excludes completed tickets. Optionally filter by status or project.",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of tickets to return (default: 50)",
                        "default": 50,
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by status (e.g., 'In Progress', 'To Do', 'Done')",
                    },
                    "project": {
                        "type": "string",
                        "description": "Filter by project key (e.g., 'PROJ')",
                    },
                    "exclude_done": {
                        "type": "boolean",
                        "description": "Exclude completed tickets (default: true)",
                        "default": True,
                    },
                },
            },
        ),
        Tool(
            name="get_available_tickets",
            description="Get unassigned tickets that are ready to be picked up. Returns tickets in the actionable status (configured via ACTIONABLE_STATUS env var, default 'To Do').",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of tickets to return (default: 50)",
                        "default": 50,
                    },
                    "status": {
                        "type": "string",
                        "description": "Override the actionable status filter",
                    },
                    "project": {
                        "type": "string",
                        "description": "Filter by project key (e.g., 'PROJ')",
                    },
                },
            },
        ),
        Tool(
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
        ),
        Tool(
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
        ),
        Tool(
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
        ),
        Tool(
            name="create_new_ticket",
            description="Create a new Jira ticket. Automatically checks for similar existing tickets before creation and warns if potential duplicates are found.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Project key (e.g., 'PROJ')",
                    },
                    "summary": {
                        "type": "string",
                        "description": "Ticket title/summary",
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed description of the ticket",
                    },
                    "issue_type": {
                        "type": "string",
                        "description": "Issue type (default: 'Task')",
                        "default": "Task",
                    },
                    "epic_key": {
                        "type": "string",
                        "description": "Epic key to link this ticket to (e.g., 'PROJ-100')",
                    },
                },
                "required": ["project", "summary"],
            },
        ),
        Tool(
            name="update_ticket_details",
            description="Update fields on an existing Jira ticket. Only provided fields will be updated.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_key": {
                        "type": "string",
                        "description": "The Jira ticket key (e.g., 'PROJ-123')",
                    },
                    "summary": {
                        "type": "string",
                        "description": "New ticket title/summary",
                    },
                    "description": {
                        "type": "string",
                        "description": "New description",
                    },
                    "assignee": {
                        "type": "string",
                        "description": "Assignee account ID or email",
                    },
                },
                "required": ["ticket_key"],
            },
        ),
        Tool(
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
        ),
    ]


def format_ticket_list(tickets: list[dict[str, Any]], header: str) -> str:
    if not tickets:
        return f"No {header.lower()} found."
    
    result_lines = [f"Found {len(tickets)} {header.lower()}:\n"]
    for ticket in tickets:
        result_lines.append(
            f"• [{ticket['key']}] {ticket['summary']}\n"
            f"  Status: {ticket['status']} | Priority: {ticket['priority']} | Project: {ticket['project']}\n"
            f"  Type: {ticket.get('type', 'N/A')} | Updated: {ticket.get('updated', 'N/A')}\n"
            f"  URL: {ticket['url']}\n"
        )
    return "\n".join(result_lines)


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name == "get_assigned_tickets":
        tickets = await fetch_assigned_tickets(
            max_results=arguments.get("max_results", 50),
            status_filter=arguments.get("status"),
            project_filter=arguments.get("project"),
            exclude_done=arguments.get("exclude_done", True),
        )
        return [TextContent(type="text", text=format_ticket_list(tickets, "ticket(s) assigned to you"))]
    
    elif name == "get_available_tickets":
        tickets = await fetch_available_tickets(
            max_results=arguments.get("max_results", 50),
            status_override=arguments.get("status"),
            project_override=arguments.get("project"),
        )
        return [TextContent(type="text", text=format_ticket_list(tickets, "available ticket(s)"))]
    
    elif name == "get_available_epics":
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
    
    elif name == "get_ticket_details":
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
    
    elif name == "search_similar_tickets":
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
    
    elif name == "create_new_ticket":
        project = arguments.get("project")
        summary = arguments.get("summary")
        if not project or not summary:
            return [TextContent(type="text", text="Error: project and summary are required")]
        
        similar = await search_similar_tickets(summary, max_results=5)
        
        warning = ""
        if similar:
            warning = f"⚠️ WARNING: Found {len(similar)} potentially similar ticket(s):\n"
            for t in similar[:3]:
                warning += f"  • [{t['key']}] {t['summary']} ({t['status']})\n"
            warning += "\nProceeding with ticket creation...\n\n"
        
        result = await create_ticket(
            project=project,
            summary=summary,
            description=arguments.get("description"),
            issue_type=arguments.get("issue_type", "Task"),
            epic_key=arguments.get("epic_key"),
        )
        
        return [TextContent(type="text", text=f"{warning}Created ticket: {result['key']}\nURL: {result['url']}")]
    
    elif name == "update_ticket_details":
        ticket_key = arguments.get("ticket_key")
        if not ticket_key:
            return [TextContent(type="text", text="Error: ticket_key is required")]
        
        result = await update_ticket(
            ticket_key=ticket_key,
            summary=arguments.get("summary"),
            description=arguments.get("description"),
            assignee=arguments.get("assignee"),
        )
        
        return [TextContent(type="text", text=f"Updated ticket: {result['key']}\nURL: {result['url']}")]
    
    elif name == "transition_ticket":
        ticket_key = arguments.get("ticket_key")
        transition_name = arguments.get("transition_name")
        if not ticket_key or not transition_name:
            return [TextContent(type="text", text="Error: ticket_key and transition_name are required")]
        
        result = await transition_ticket(ticket_key, transition_name)
        
        return [TextContent(type="text", text=f"Transitioned {result['key']} to: {result['new_status']}\nURL: {result['url']}")]
    
    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def run_server():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
