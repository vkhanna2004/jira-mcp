import os
import sys
import logging
from dotenv import load_dotenv
from fastmcp import FastMCP

from src.jira_client import JiraClient, JiraClientError

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Initialize Jira client
try:
    jira_client = JiraClient(
        url=os.getenv("JIRA_BASE_URL"),
        email=os.getenv("JIRA_EMAIL"),
        api_token=os.getenv("JIRA_API_TOKEN")
    )
    logger.info("Jira client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Jira client: {e}")
    sys.exit(1)

# Initialize FastMCP server
mcp = FastMCP("Jira MCP Server")

@mcp.tool()
def create_project(project_name: str, project_key: str, board_type: str = "kanban") -> dict:
    """
    Create a new Jira software project with an associated board.
    
    Jira doesn't have a direct "create board" API. This creates a software
    project with a template that automatically includes a board.
    """
    try:
        logger.info(f"Creating {board_type} board: {project_name} ({project_key})")
        result = jira_client.create_project(project_name, project_key, board_type)
        logger.info("Project created successfully")
        return result
    except JiraClientError as e:
        logger.error(f"Failed to create board: {e}")
        return {"error": str(e)}


@mcp.tool()
def create_issue(
    summary: str,
    project_key: str = "",
    project_name: str = "",
    description: str = "",
    issue_type: str = "Task",
    assignee: str = "",
    priority: str = "",
    labels: list = [],
    due_date: str = ""
) -> dict:
    """
    Create a new Jira issue with optional fields.
    """
    try:
        logger.info(f"Creating issue: {summary}")
        result = jira_client.create_issue(
            summary=summary,
            description=description,
            project_key=project_key if project_key else None,
            project_name=project_name if project_name else None,
            issue_type=issue_type,
            assignee=assignee if assignee else None,
            priority=priority if priority else None,
            labels=labels if labels else None,
            due_date=due_date if due_date else None
        )
        logger.info(f"Issue created successfully: {result}")
        return result
    except JiraClientError as e:
        logger.error(f"Failed to create issue: {e}")
        return {"error": str(e)}

@mcp.tool()
def search_issues(query: str) -> dict:
    """
    Search for Jira issues using JQL (Jira Query Language).
    
    Examples:
        - 'project = TEST AND status = "To Do"'
        - 'assignee = currentUser() AND priority = High'
        - 'created >= -7d ORDER BY created DESC'
        - 'labels = bug AND status != Done'
    """
    try:
        logger.info(f"Searching issues: {query}")
        result = jira_client.search_issues(query)
        issue_count = len(result.get("issues", []))
        logger.info(f"Found {issue_count} issues")
        return result
    except JiraClientError as e:
        logger.error(f"Failed to search issues: {e}")
        return {"error": str(e)}


@mcp.tool()
def add_comment(issue_id: str, comment: str) -> dict:
    """
    Add a comment to an existing Jira issue.
    """
    try:
        logger.info(f"Adding comment to {issue_id}")
        result = jira_client.add_comment(issue_id, comment)
        logger.info(f"Comment added successfully to {issue_id}")
        return result
    except JiraClientError as e:
        logger.error(f"Failed to add comment: {e}")
        return {"error": str(e)}

@mcp.tool()
def change_status(issue_id: str, new_status: str) -> dict:
    """
    Change the status/workflow state of a Jira issue.

    The status must be available in the issue's workflow. If the requested status
    is not available, the response will include a list of valid status options.
    """
    try:
        issue_id = str(issue_id)
        new_status = str(new_status)
        
        logger.info(f"Changing status of {issue_id} to '{new_status}' (type: {type(new_status)})")
        result = jira_client.change_status(issue_id, new_status)
        logger.info("Status changed successfully")
        return result
    except JiraClientError as e:
        logger.error(f"Failed to change status: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error in change_status: {e}", exc_info=True)
        return {"error": str(e)}


if __name__ == "__main__":
    logger.info("Starting Jira MCP server with FastMCP...")
    mcp.run()