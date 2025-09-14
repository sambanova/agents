"""
Atlassian Direct REST API Connector

Provides direct integration with Atlassian REST APIs (Jira and Confluence)
without using the MCP server, since the MCP server is still in beta.
"""

import json
from typing import Any, Dict, List, Optional

import httpx
import structlog
from langchain.callbacks.manager import AsyncCallbackManagerForToolRun
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class JiraSearchTool(BaseTool):
    """Tool for searching Jira issues using REST API"""
    
    name: str = "jira_search_issues"
    description: str = "Search for Jira issues using JQL"
    
    access_token: str
    cloud_id: str
    
    class Args(BaseModel):
        jql: str = Field(description="JQL query string")
        max_results: int = Field(default=10, description="Maximum number of results")
        fields: List[str] = Field(
            default_factory=lambda: ["summary", "status", "priority", "assignee"],
            description="Fields to include"
        )
    
    args_schema = Args
    
    async def _arun(
        self,
        jql: str,
        max_results: int = 10,
        fields: List[str] = None,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Execute Jira search"""
        try:
            if fields is None:
                fields = ["summary", "status", "priority", "assignee"]
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.atlassian.com/ex/jira/{self.cloud_id}/rest/api/3/search/jql",
                    params={
                        "jql": jql,
                        "maxResults": max_results,
                        "fields": ",".join(fields)
                    },
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Accept": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    issues = data.get("issues", [])
                    
                    if not issues:
                        return "No issues found matching your query."
                    
                    # Format the results
                    results = []
                    for issue in issues:
                        issue_data = {
                            "key": issue["key"],
                            "summary": issue["fields"].get("summary", "No summary"),
                            "status": issue["fields"].get("status", {}).get("name", "Unknown"),
                            "priority": issue["fields"].get("priority", {}).get("name", "None") if issue["fields"].get("priority") else "None",
                            "assignee": issue["fields"].get("assignee", {}).get("displayName", "Unassigned") if issue["fields"].get("assignee") else "Unassigned"
                        }
                        results.append(issue_data)
                    
                    return json.dumps(results, indent=2)
                elif response.status_code == 400:
                    error_data = response.json()
                    error_messages = error_data.get("errorMessages", [])
                    if error_messages:
                        return f"Invalid JQL query: {', '.join(error_messages)}"
                    return f"Bad request: {response.text}"
                elif response.status_code == 401:
                    return "Authentication failed. Please reconnect your Jira account."
                elif response.status_code == 403:
                    return "Permission denied. You don't have access to search these issues."
                elif response.status_code == 410:
                    return "This API endpoint has been removed. Please contact support to update the integration."
                else:
                    return f"Error searching Jira: {response.status_code} - {response.text}"
                    
        except Exception as e:
            logger.error("Jira search failed", error=str(e), exc_info=True)
            return f"Error searching Jira: {str(e)}"
    
    def _run(self, *args, **kwargs):
        """Sync execution not supported"""
        raise NotImplementedError("Use async execution")


class CreateJiraIssueTool(BaseTool):
    """Tool for creating Jira issues using REST API"""
    
    name: str = "jira_create_issue"
    description: str = "Create a new issue in Jira"
    
    access_token: str
    cloud_id: str
    
    class Args(BaseModel):
        project: str = Field(description="Project key")
        summary: str = Field(description="Issue summary")
        description: str = Field(default="", description="Issue description")
        issue_type: str = Field(default="Task", description="Issue type")
        priority: str = Field(default="Medium", description="Priority")
    
    args_schema = Args
    
    async def _arun(
        self,
        project: str,
        summary: str,
        description: str = "",
        issue_type: str = "Task",
        priority: str = "Medium",
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Create a Jira issue"""
        try:
            # Map priority names to IDs (common defaults)
            priority_map = {
                "Highest": "1",
                "High": "2",
                "Medium": "3",
                "Low": "4",
                "Lowest": "5"
            }
            
            issue_data = {
                "fields": {
                    "project": {"key": project},
                    "summary": summary,
                    "description": {
                        "type": "doc",
                        "version": 1,
                        "content": [{
                            "type": "paragraph",
                            "content": [{
                                "type": "text",
                                "text": description or "No description provided"
                            }]
                        }]
                    },
                    "issuetype": {"name": issue_type},
                    "priority": {"id": priority_map.get(priority, "3")}
                }
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.atlassian.com/ex/jira/{self.cloud_id}/rest/api/3/issue",
                    json=issue_data,
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Accept": "application/json",
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code in [200, 201]:
                    data = response.json()
                    return f"Successfully created issue: {data['key']} - {summary}"
                elif response.status_code == 400:
                    error_data = response.json()
                    errors = error_data.get("errors", {})
                    error_messages = error_data.get("errorMessages", [])
                    if errors:
                        error_details = [f"{field}: {msg}" for field, msg in errors.items()]
                        return f"Invalid issue data: {', '.join(error_details)}"
                    elif error_messages:
                        return f"Invalid issue data: {', '.join(error_messages)}"
                    return f"Bad request: {response.text}"
                elif response.status_code == 401:
                    return "Authentication failed. Please reconnect your Jira account."
                elif response.status_code == 403:
                    return "Permission denied. You don't have permission to create issues in this project."
                elif response.status_code == 404:
                    return "Project not found. Please check the project key."
                else:
                    return f"Error creating issue: {response.status_code} - {response.text}"
                    
        except Exception as e:
            logger.error("Failed to create Jira issue", error=str(e), exc_info=True)
            return f"Error creating issue: {str(e)}"
    
    def _run(self, *args, **kwargs):
        """Sync execution not supported"""
        raise NotImplementedError("Use async execution")


async def get_atlassian_cloud_id(access_token: str) -> Optional[str]:
    """Get the Atlassian Cloud ID for the user's instance"""
    try:
        logger.info(
            "Getting Atlassian Cloud ID",
            has_token=bool(access_token),
            token_preview=access_token[:20] if access_token else None
        )
        
        async with httpx.AsyncClient() as client:
            # For Atlassian, we need to use the exact token format they expect
            # The accessible-resources endpoint is part of the OAuth flow, not the API itself
            response = await client.get(
                "https://api.atlassian.com/oauth/token/accessible-resources",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json"
                    # Don't include Content-Type for GET requests
                },
                timeout=10.0
            )
            
            logger.info(
                "Atlassian accessible-resources response",
                status_code=response.status_code,
                headers=dict(response.headers)
            )
            
            if response.status_code == 200:
                resources = response.json()
                if resources and len(resources) > 0:
                    # Return the first cloud ID
                    cloud_id = resources[0].get("id")
                    logger.info(
                        "Got Atlassian Cloud ID",
                        cloud_id=cloud_id,
                        site_name=resources[0].get("name"),
                        site_url=resources[0].get("url")
                    )
                    return cloud_id
                else:
                    logger.warning("No accessible resources found")
            elif response.status_code == 401:
                # Log detailed error information
                logger.error(
                    "Atlassian token authentication failed",
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    response_text=response.text[:500] if response.text else None
                )
                
                # Try to decode the token to see what's in it (JWT)
                try:
                    import base64
                    import json as json_lib
                    # JWT tokens have 3 parts separated by dots
                    parts = access_token.split('.')
                    if len(parts) >= 2:
                        # Decode the payload (second part)
                        payload = parts[1]
                        # Add padding if needed
                        padding = 4 - len(payload) % 4
                        if padding != 4:
                            payload += '=' * padding
                        decoded = base64.urlsafe_b64decode(payload)
                        token_data = json_lib.loads(decoded)
                        logger.info(
                            "Token payload decoded",
                            iss=token_data.get("iss"),
                            sub=token_data.get("sub"),
                            aud=token_data.get("aud"),
                            scope=token_data.get("scope"),
                            exp=token_data.get("exp")
                        )
                except Exception as e:
                    logger.debug("Could not decode token", error=str(e))
            else:
                logger.error(
                    f"Unexpected status code: {response.status_code}",
                    response_text=response.text[:500] if response.text else None
                )
        return None
    except Exception as e:
        logger.error("Failed to get Atlassian Cloud ID", error=str(e), exc_info=True)
        return None


async def create_atlassian_direct_tools(
    access_token: str,
    tool_ids: List[str]
) -> List[BaseTool]:
    """Create Atlassian tools using direct REST API"""
    tools = []
    
    # Get Cloud ID first
    cloud_id = await get_atlassian_cloud_id(access_token)
    if not cloud_id:
        logger.error("Could not get Atlassian Cloud ID")
        return []
    
    # Create requested tools
    tool_map = {
        "jira_search_issues": JiraSearchTool,
        "jira_create_issue": CreateJiraIssueTool,
    }
    
    for tool_id in tool_ids:
        if tool_id in tool_map:
            tool_class = tool_map[tool_id]
            tool = tool_class(
                access_token=access_token,
                cloud_id=cloud_id
            )
            tools.append(tool)
            logger.info(f"Created Atlassian direct tool: {tool_id}")
    
    return tools