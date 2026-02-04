from typing import Any

from mcp.types import Tool, TextContent

from ..config import (
    PROJECT_KEYS,
    get_default_project,
    set_default_project,
    get_default_sprint_id,
    set_default_sprint_id,
)


tool = Tool(
    name="update_config",
    description=f"Update MCP configuration settings. Changes are saved to config.json and persist across restarts. Available projects: {', '.join(PROJECT_KEYS) if PROJECT_KEYS else 'none configured'}. Use list_sprints to find sprint IDs.",
    inputSchema={
        "type": "object",
        "properties": {
            "default_project": {
                "type": "string",
                "description": f"Set the default project for ticket creation. Must be one of: {', '.join(PROJECT_KEYS) if PROJECT_KEYS else 'none configured'}",
                "enum": PROJECT_KEYS if PROJECT_KEYS else None,
            },
            "default_sprint_id": {
                "type": "integer",
                "description": "Set the default sprint ID for ticket creation. Use list_sprints to see available sprints.",
            },
        },
    },
)


async def handler(arguments: dict[str, Any]) -> list[TextContent]:
    if not arguments:
        # Show current config
        current = {
            "default_project": get_default_project() or "(not set)",
            "default_sprint_id": get_default_sprint_id() or "(not set)",
        }
        lines = ["Current configuration:"]
        for key, value in current.items():
            lines.append(f"  • {key}: {value}")
        return [TextContent(type="text", text="\n".join(lines))]
    
    changes = []
    
    # Handle default_project
    if "default_project" in arguments:
        project_key = arguments["default_project"]
        if project_key:
            project_key = project_key.upper()
            if PROJECT_KEYS and project_key not in PROJECT_KEYS:
                return [TextContent(type="text", text=f"Error: '{project_key}' is not a configured project. Available: {', '.join(PROJECT_KEYS)}")]
            old = get_default_project()
            set_default_project(project_key)
            if old and old != project_key:
                changes.append(f"default_project: {old} → {project_key}")
            else:
                changes.append(f"default_project: {project_key}")
    
    # Handle default_sprint_id
    if "default_sprint_id" in arguments:
        sprint_id = arguments["default_sprint_id"]
        if sprint_id is not None:
            old = get_default_sprint_id()
            set_default_sprint_id(sprint_id)
            if old and old != str(sprint_id):
                changes.append(f"default_sprint_id: {old} → {sprint_id}")
            else:
                changes.append(f"default_sprint_id: {sprint_id}")
    
    if not changes:
        return [TextContent(type="text", text="No changes made. Provide at least one setting to update.")]
    
    return [TextContent(type="text", text="Updated configuration:\n  • " + "\n  • ".join(changes))]
