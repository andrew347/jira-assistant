from .get_assigned_tickets import tool as get_assigned_tickets_tool, handler as get_assigned_tickets_handler
from .get_available_tickets import tool as get_available_tickets_tool, handler as get_available_tickets_handler
from .get_available_epics import tool as get_available_epics_tool, handler as get_available_epics_handler
from .get_epic_tickets import tool as get_epic_tickets_tool, handler as get_epic_tickets_handler
from .get_ticket_details import tool as get_ticket_details_tool, handler as get_ticket_details_handler
from .search_similar_tickets import tool as search_similar_tickets_tool, handler as search_similar_tickets_handler
from .create_new_ticket import tool as create_new_ticket_tool, handler as create_new_ticket_handler
from .create_new_epic import tool as create_new_epic_tool, handler as create_new_epic_handler
from .update_ticket_details import tool as update_ticket_details_tool, handler as update_ticket_details_handler
from .add_ticket_comment import tool as add_ticket_comment_tool, handler as add_ticket_comment_handler
from .list_sprints import tool as list_sprints_tool, handler as list_sprints_handler
from .update_config import tool as update_config_tool, handler as update_config_handler

ALL_TOOLS = [
    get_assigned_tickets_tool,
    get_available_tickets_tool,
    get_available_epics_tool,
    get_epic_tickets_tool,
    get_ticket_details_tool,
    search_similar_tickets_tool,
    create_new_ticket_tool,
    create_new_epic_tool,
    update_ticket_details_tool,
    add_ticket_comment_tool,
    list_sprints_tool,
    update_config_tool,
]

TOOL_HANDLERS = {
    "get_assigned_tickets": get_assigned_tickets_handler,
    "get_available_tickets": get_available_tickets_handler,
    "get_available_epics": get_available_epics_handler,
    "get_epic_tickets": get_epic_tickets_handler,
    "get_ticket_details": get_ticket_details_handler,
    "search_similar_tickets": search_similar_tickets_handler,
    "create_new_ticket": create_new_ticket_handler,
    "create_new_epic": create_new_epic_handler,
    "update_ticket_details": update_ticket_details_handler,
    "add_ticket_comment": add_ticket_comment_handler,
    "list_sprints": list_sprints_handler,
    "update_config": update_config_handler,
}
