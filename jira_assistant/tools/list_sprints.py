from typing import Any

import httpx
from mcp.types import Tool, TextContent

from ..config import JIRA_HOST, PROJECT_KEYS, get_auth_header, get_default_sprint_id


tool = Tool(
    name="list_sprints",
    description="List available sprints from Jira boards. Shows active and future sprints with their IDs, which can be used with update_config to set the default sprint for ticket creation.",
    inputSchema={
        "type": "object",
        "properties": {
            "board_id": {
                "type": "integer",
                "description": "Specific board ID to fetch sprints from. If not provided, searches for boards in configured projects.",
            },
            "include_closed": {
                "type": "boolean",
                "description": "Include closed sprints in results (default: false)",
                "default": False,
            },
        },
    },
)


async def fetch_boards(project_key: str) -> list[dict[str, Any]]:
    """Fetch Scrum/Kanban boards for a project."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{JIRA_HOST}/rest/agile/1.0/board",
            params={"projectKeyOrId": project_key},
            headers={
                "Authorization": get_auth_header(),
                "Accept": "application/json",
            },
        )
        if not response.is_success:
            return []
        data = response.json()
    
    return [
        {"id": b["id"], "name": b["name"], "type": b.get("type", "unknown")}
        for b in data.get("values", [])
    ]


async def fetch_sprints(board_id: int, include_closed: bool = False) -> list[dict[str, Any]]:
    """Fetch sprints for a board."""
    states = "active,future"
    if include_closed:
        states = "active,future,closed"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{JIRA_HOST}/rest/agile/1.0/board/{board_id}/sprint",
            params={"state": states},
            headers={
                "Authorization": get_auth_header(),
                "Accept": "application/json",
            },
        )
        if not response.is_success:
            error_detail = response.text
            raise Exception(f"Jira API error {response.status_code}: {error_detail}")
        data = response.json()
    
    sprints = []
    for s in data.get("values", []):
        sprints.append({
            "id": s["id"],
            "name": s["name"],
            "state": s.get("state", "unknown"),
            "start_date": s.get("startDate"),
            "end_date": s.get("endDate"),
            "board_id": board_id,
        })
    
    return sprints


async def handler(arguments: dict[str, Any]) -> list[TextContent]:
    board_id = arguments.get("board_id")
    include_closed = arguments.get("include_closed", False)
    
    current_sprint_id = get_default_sprint_id()
    
    all_sprints: list[dict[str, Any]] = []
    boards_checked: list[str] = []
    
    if board_id:
        # Fetch from specific board
        sprints = await fetch_sprints(board_id, include_closed)
        all_sprints.extend(sprints)
        boards_checked.append(f"Board {board_id}")
    else:
        # Search for boards in configured projects
        if not PROJECT_KEYS:
            return [TextContent(type="text", text="Error: No PROJECT_KEYS configured. Set PROJECT_KEYS in .env or provide a board_id.")]
        
        for project_key in PROJECT_KEYS:
            boards = await fetch_boards(project_key)
            for board in boards:
                boards_checked.append(f"{board['name']} ({board['type']})")
                try:
                    sprints = await fetch_sprints(board["id"], include_closed)
                    all_sprints.extend(sprints)
                except Exception:
                    # Skip boards that don't support sprints (e.g., Kanban)
                    pass
    
    if not all_sprints:
        return [TextContent(type="text", text=f"No sprints found. Boards checked: {', '.join(boards_checked)}")]
    
    # Deduplicate sprints (same sprint can appear on multiple boards)
    seen_ids = set()
    unique_sprints = []
    for s in all_sprints:
        if s["id"] not in seen_ids:
            seen_ids.add(s["id"])
            unique_sprints.append(s)
    
    # Sort: active first, then future, then closed
    state_order = {"active": 0, "future": 1, "closed": 2}
    unique_sprints.sort(key=lambda s: (state_order.get(s["state"], 99), s["id"]))
    
    # Format output
    lines = [f"Found {len(unique_sprints)} sprint(s):\n"]
    
    if current_sprint_id:
        lines.append(f"Current default sprint ID: {current_sprint_id}\n")
    
    for sprint in unique_sprints:
        marker = " (current default)" if str(sprint["id"]) == current_sprint_id else ""
        dates = ""
        if sprint["start_date"] and sprint["end_date"]:
            start = sprint["start_date"][:10]  # Just the date part
            end = sprint["end_date"][:10]
            dates = f" | {start} to {end}"
        
        lines.append(
            f"• [{sprint['state'].upper()}] {sprint['name']}{marker}\n"
            f"  ID: {sprint['id']}{dates}\n"
        )
    
    lines.append("\nUse update_config with default_sprint_id to change the default.")
    
    return [TextContent(type="text", text="\n".join(lines))]
