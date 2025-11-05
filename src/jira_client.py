import logging
from typing import Optional, List, Dict, Any
from atlassian import Jira

logger = logging.getLogger(__name__)

class JiraClientError(Exception):
    """Base exception for Jira client errors."""
    pass

class JiraClient:
    
    def __init__(self, url: str, email: str, api_token: str):
        """
        Initialize Jira client with credentials.
        
        Args:
            url: Jira base URL
            email: Jira email
            api_token: Jira API token
            
        Raises:
            JiraClientError: If connection fails
        """
        try:
            self.jira = Jira(
                url=url,
                username=email,
                password=api_token
            )
            self.url = url
            self.email = email
            logger.info(f"Jira client initialized for {email[:3]}***")
        except Exception as e:
            logger.error(f"Failed to initialize Jira client: {str(e)}")
            raise JiraClientError(f"Failed to initialize Jira client: {str(e)}")

    def get_current_user_account_id(self) -> str:
        """
        Get the account ID of the currently authenticated user.
        """
        try:
            myself = self.jira.myself()
            account_id = myself.get("accountId")
            if not account_id:
                raise JiraClientError("Unable to retrieve account ID")
            logger.info(f"Retrieved account ID: {account_id}")
            return account_id
        except Exception as e:
            logger.error(f"Failed to get current user account ID: {str(e)}")
            raise JiraClientError(f"Failed to get current user account ID: {str(e)}")

    def create_project(
        self, 
        project_name: str, 
        project_key: str, 
        board_type: str = "scrum"
    ) -> Dict[str, Any]:
        """
        Create a new Jira project with an associated board.
        
        Note: Jira doesn't have a direct "create board" API. This creates a software
        project with a template that automatically includes a board.
        """
        try:
            # Validate project key
            if not project_key.isupper() or not (2 <= len(project_key) <= 10):
                raise JiraClientError(
                    "Project key must be 2-10 uppercase letters (e.g., 'PROJ', 'TEST')"
                )
            
            # Get current user's account ID
            account_id = self.get_current_user_account_id()
            
            # Determine project template based on board type
            if board_type.lower() == "kanban":
                template = "com.pyxis.greenhopper.jira:gh-kanban-template"
            elif board_type.lower() == "scrum":
                template = "com.pyxis.greenhopper.jira:gh-scrum-template"
            else:
                raise JiraClientError(
                    f"Invalid board_type '{board_type}'. Must be 'scrum' or 'kanban'"
                )
            
            payload = {
                "key": project_key,
                "name": project_name,
                "projectTypeKey": "software",
                "projectTemplateKey": template,
                "leadAccountId": account_id,
                "assigneeType": "UNASSIGNED"
            }
            
            logger.info(f"Creating project: {project_name} ({project_key}) with {board_type} board")
            result = self.jira.post("/rest/api/3/project", data=payload)
            
            # Get the board that was auto-created
            board_info = self._get_board_for_project(project_key)
            
            success_response = {
                "success": True,
                "project_key": result.get("key"),
                "project_id": result.get("id"),
                "project_url": f"{self.url}/browse/{result.get('key')}",
                "board_id": board_info.get("id"),
                "board_url": f"{self.url}/jira/software/c/projects/{project_key}/boards/{board_info.get('id')}",
                "board_type": board_type,
                "message": f"Successfully created {board_type} board '{project_name}' with project key {project_key}"
            }
            
            logger.info(f"Board created successfully: {success_response}")
            return success_response
            
        except JiraClientError:
            raise
        except Exception as e:
            logger.error(f"Failed to create board: {str(e)}")
            raise JiraClientError(f"Failed to create board: {str(e)}")

    def _get_board_for_project(self, project_key: str) -> Dict[str, Any]:
        """
        Get the board associated with a project.
        """
        try:
            # Use Jira Agile API to get boards for project
            response = self.jira.get(
                f"/rest/agile/1.0/board?projectKeyOrId={project_key}"
            )
            boards = response.get("values", [])
            if boards:
                return boards[0]  # Return first board
            return {}
        except Exception as e:
            logger.warning(f"Could not retrieve board info: {str(e)}")
            return {}

    def get_project_key_by_name(self, project_name: str) -> str:
        """
        Fetch the project key based on the project name.
        """
        try:
            projects = self.jira.projects()
            for project in projects:
                if project.name.lower() == project_name.lower():
                    logger.info(f"Found project: {project_name} -> {project.key}")
                    return project.key
            raise JiraClientError(f"Project '{project_name}' not found")
        except JiraClientError:
            raise
        except Exception as e:
            logger.error(f"Failed to get project key: {str(e)}")
            raise JiraClientError(f"Failed to get project key: {str(e)}")

    def create_issue(
        self,
        project_key: Optional[str] = None,
        project_name: Optional[str] = None,
        summary: str = "",
        description: str = "",
        issue_type: str = "Task",
        assignee: Optional[str] = None,
        priority: Optional[str] = None,
        labels: Optional[List[str]] = None,
        due_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a Jira issue with optional fields.
        """
        try:
            if not summary:
                raise JiraClientError("Summary is required")
            
            # Resolve project key
            if not project_key and project_name:
                project_key = self.get_project_key_by_name(project_name)
            
            if not project_key:
                raise JiraClientError("Either project_key or project_name must be provided")

            issue = {
                "fields": {
                    "project": {"key": project_key},
                    "summary": summary,
                    "description": description,
                    "issuetype": {"name": issue_type}
                }
            }
            
            # optional fields
            if assignee:
                issue["fields"]["assignee"] = {"name": assignee}
            if priority:
                issue["fields"]["priority"] = {"name": priority}
            if labels:
                issue["fields"]["labels"] = labels
            if due_date:
                issue["fields"]["duedate"] = due_date
            
            result = self.jira.issue_create(fields=issue["fields"])
            
            issue_key = result.get("key")
            return {
                "success": True,
                "issue_key": issue_key,
                "issue_id": result.get("id"),
                "issue_url": f"{self.url}/browse/{issue_key}",
                "message": f"Successfully created issue {issue_key}"
            }
            
        except JiraClientError:
            raise
        except Exception as e:
            logger.error(f"Failed to create issue: {str(e)}")
            raise JiraClientError(f"Failed to create issue: {str(e)}")
    
    def search_issues(self, query: str, max_results: int = 10) -> Dict[str, Any]:
        """
        Search issues using JQL.
        """
        try:
            if not query:
                raise JiraClientError("Query cannot be empty")
            
            # Use the new API v3 endpoint
            payload = {
                "jql": query,
                "maxResults": max_results,
                "fields": ["summary", "status", "assignee", "issuetype", "priority", "created"]
            }
            
            results = self.jira.post("/rest/api/3/search/jql", data=payload)
            issue_count = len(results.get('issues', []))
            
            # Simplify response
            simplified_issues = []
            for issue in results.get('issues', []):
                assignee_data = issue.get("fields", {}).get("assignee")
                assignee_name = assignee_data.get("displayName") if assignee_data else "Unassigned"
                
                simplified_issues.append({
                    "key": issue.get("key"),
                    "summary": issue.get("fields", {}).get("summary"),
                    "status": issue.get("fields", {}).get("status", {}).get("name"),
                    "assignee": assignee_name,
                    "priority": issue.get("fields", {}).get("priority", {}).get("name", "None"),
                    "issue_type": issue.get("fields", {}).get("issuetype", {}).get("name"),
                    "url": f"{self.url}/browse/{issue.get('key')}"
                })
            
            logger.info(f"Found {issue_count} issues")
            return {
                "success": True,
                "total": results.get("total", issue_count),
                "returned": issue_count,
                "issues": simplified_issues
            }
        except Exception as e:
            logger.error(f"Failed to search issues: {str(e)}")
            raise JiraClientError(f"Failed to search issues: {str(e)}")

    def add_comment(self, issue_id: str, comment: str) -> Dict[str, Any]:
        """
        Add a comment to a Jira issue.
        """
        try:
            if not issue_id or not comment:
                raise JiraClientError("Issue ID and comment are required")
            
            result = self.jira.issue_add_comment(issue_id, comment)
            logger.info(f"Comment added to {issue_id}")
            return {
                "success": True,
                "issue_id": issue_id,
                "comment_id": result.get("id"),
                "message": f"Successfully added comment to {issue_id}"
            }
        except Exception as e:
            logger.error(f"Failed to add comment: {str(e)}")
            raise JiraClientError(f"Failed to add comment: {str(e)}")
    
    def change_status(self, issue_id: str, new_status: str) -> Dict[str, Any]:
        """
        Change the status/workflow state of a Jira issue.
        Returns: Dictionary with status change response or available statuses if unsuccessful
        """
        try:
            if not issue_id or not new_status:
                raise JiraClientError("Issue ID and new status are required")

            # Get available transitions for this issue
            transitions_response = self.jira.get_issue_transitions(issue_id)

            # Handle both dict and list responses
            if isinstance(transitions_response, dict):
                transitions = transitions_response.get("transitions", [])
            elif isinstance(transitions_response, list):
                transitions = transitions_response
            else:
                raise JiraClientError("Unexpected response format from get_issue_transitions")

            # Find the target transition
            target = None
            for t in transitions:
                transition_name = t.get("name", "")
                if isinstance(transition_name, str) and transition_name.lower() == new_status.lower():
                    target = t
                    break
                
            if not target:
                available = [t.get("name", "Unknown") for t in transitions if isinstance(t.get("name"), str)]
                raise JiraClientError(
                    f"Status '{new_status}' not available. Available transitions: {', '.join(available)}"
                )

            # Perform the status change
            transition_id = target.get("id")
            result = self.jira.set_issue_status_by_transition_id(issue_id, transition_id)
            logger.info(f"Status changed for {issue_id} to {new_status}")
            return {
                "success": True,
                "issue_id": issue_id,
                "new_status": new_status,
                "transition_id": str(transition_id),
                "message": f"Successfully changed {issue_id} status to {new_status}"
            }
        except JiraClientError:
            raise
        except Exception as e:
            logger.error(f"Failed to change status: {str(e)}")
            raise JiraClientError(f"Failed to change status: {str(e)}")
