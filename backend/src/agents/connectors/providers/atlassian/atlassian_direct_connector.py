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


class JiraGetIssueTool(BaseTool):
    """Tool for getting a Jira issue by key"""
    
    name: str = "jira_get_issue"
    description: str = "Get details of a specific Jira issue"
    
    access_token: str
    cloud_id: str
    
    class Args(BaseModel):
        issue_key: str = Field(description="Issue key (e.g., PROJ-123)")
        fields: List[str] = Field(
            default_factory=lambda: ["summary", "status", "priority", "assignee", "description", "created", "updated"],
            description="Fields to include"
        )
    
    args_schema = Args
    
    async def _arun(
        self,
        issue_key: str,
        fields: List[str] = None,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Get Jira issue details"""
        try:
            if fields is None:
                fields = ["summary", "status", "priority", "assignee", "description", "created", "updated"]
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.atlassian.com/ex/jira/{self.cloud_id}/rest/api/3/issue/{issue_key}",
                    params={
                        "fields": ",".join(fields)
                    },
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Accept": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    issue = response.json()
                    
                    # Format the result
                    issue_data = {
                        "key": issue["key"],
                        "summary": issue["fields"].get("summary", "No summary"),
                        "status": issue["fields"].get("status", {}).get("name", "Unknown"),
                        "priority": issue["fields"].get("priority", {}).get("name", "None") if issue["fields"].get("priority") else "None",
                        "assignee": issue["fields"].get("assignee", {}).get("displayName", "Unassigned") if issue["fields"].get("assignee") else "Unassigned",
                        "description": issue["fields"].get("description", "No description"),
                        "created": issue["fields"].get("created"),
                        "updated": issue["fields"].get("updated")
                    }
                    
                    return json.dumps(issue_data, indent=2)
                elif response.status_code == 404:
                    return f"Issue not found: {issue_key}"
                else:
                    return f"Error getting issue: {response.status_code} - {response.text}"
                    
        except Exception as e:
            logger.error("Failed to get Jira issue", error=str(e), exc_info=True)
            return f"Error getting issue: {str(e)}"
    
    def _run(self, *args, **kwargs):
        """Sync execution not supported"""
        raise NotImplementedError("Use async execution")


class JiraUpdateIssueTool(BaseTool):
    """Tool for updating a Jira issue"""
    
    name: str = "jira_update_issue"
    description: str = "Update an existing Jira issue"
    
    access_token: str
    cloud_id: str
    
    class Args(BaseModel):
        issue_key: str = Field(description="Issue key (e.g., PROJ-123)")
        summary: Optional[str] = Field(default=None, description="New summary")
        description: Optional[str] = Field(default=None, description="New description")
        priority: Optional[str] = Field(default=None, description="New priority")
        assignee: Optional[str] = Field(default=None, description="New assignee account ID")
        status: Optional[str] = Field(default=None, description="New status (e.g., Done, In Progress, Blocked)")
    
    args_schema = Args
    
    async def _arun(
        self,
        issue_key: str,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[str] = None,
        assignee: Optional[str] = None,
        status: Optional[str] = None,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Update Jira issue"""
        try:
            # Handle status transitions first if requested
            if status:
                # Get available transitions for the issue
                async with httpx.AsyncClient() as client:
                    transitions_response = await client.get(
                        f"https://api.atlassian.com/ex/jira/{self.cloud_id}/rest/api/3/issue/{issue_key}/transitions",
                        headers={
                            "Authorization": f"Bearer {self.access_token}",
                            "Accept": "application/json"
                        }
                    )

                    if transitions_response.status_code != 200:
                        logger.error(f"Failed to get transitions: {transitions_response.status_code}")
                        return f"Failed to get available transitions for issue {issue_key}"

                    transitions = transitions_response.json().get("transitions", [])

                    # Find the transition that matches the requested status
                    transition_id = None
                    for transition in transitions:
                        if transition["to"]["name"].lower() == status.lower():
                            transition_id = transition["id"]
                            break

                    if not transition_id:
                        available_statuses = [t["to"]["name"] for t in transitions]
                        return f"Status '{status}' not available. Available statuses: {', '.join(available_statuses)}"

                    # Execute the transition
                    transition_data = {
                        "transition": {"id": transition_id}
                    }

                    transition_response = await client.post(
                        f"https://api.atlassian.com/ex/jira/{self.cloud_id}/rest/api/3/issue/{issue_key}/transitions",
                        json=transition_data,
                        headers={
                            "Authorization": f"Bearer {self.access_token}",
                            "Accept": "application/json",
                            "Content-Type": "application/json"
                        }
                    )

                    if transition_response.status_code not in [200, 204]:
                        logger.error(f"Failed to transition status: {transition_response.status_code} - {transition_response.text}")
                        return f"Failed to update status to '{status}': {transition_response.text}"

            # Build update payload for other fields
            update_data = {"fields": {}}
            
            if summary:
                update_data["fields"]["summary"] = summary
            
            if description:
                update_data["fields"]["description"] = {
                    "type": "doc",
                    "version": 1,
                    "content": [{
                        "type": "paragraph",
                        "content": [{
                            "type": "text",
                            "text": description
                        }]
                    }]
                }
            
            if priority:
                priority_map = {
                    "Highest": "1",
                    "High": "2",
                    "Medium": "3",
                    "Low": "4",
                    "Lowest": "5"
                }
                update_data["fields"]["priority"] = {"id": priority_map.get(priority, "3")}
            
            if assignee:
                update_data["fields"]["assignee"] = {"accountId": assignee}

            # Only make the update call if there are fields to update
            if update_data["fields"]:
                async with httpx.AsyncClient() as client:
                    response = await client.put(
                        f"https://api.atlassian.com/ex/jira/{self.cloud_id}/rest/api/3/issue/{issue_key}",
                        json=update_data,
                        headers={
                            "Authorization": f"Bearer {self.access_token}",
                            "Accept": "application/json",
                            "Content-Type": "application/json"
                        }
                    )

                    if response.status_code not in [200, 204]:
                        if response.status_code == 404:
                            return f"Issue not found: {issue_key}"
                        else:
                            return f"Error updating issue fields: {response.status_code} - {response.text}"

            # Build success message
            updated_items = []
            if status:
                updated_items.append(f"status to '{status}'")
            if summary:
                updated_items.append("summary")
            if description:
                updated_items.append("description")
            if priority:
                updated_items.append(f"priority to '{priority}'")
            if assignee:
                updated_items.append("assignee")

            if updated_items:
                return f"Successfully updated issue {issue_key}: {', '.join(updated_items)}"
            else:
                return f"No fields to update for issue {issue_key}"
                    
        except Exception as e:
            logger.error("Failed to update Jira issue", error=str(e), exc_info=True)
            return f"Error updating issue: {str(e)}"
    
    def _run(self, *args, **kwargs):
        """Sync execution not supported"""
        raise NotImplementedError("Use async execution")


class JiraAddCommentTool(BaseTool):
    """Tool for adding a comment to a Jira issue"""
    
    name: str = "jira_add_comment"
    description: str = "Add a comment to a Jira issue"
    
    access_token: str
    cloud_id: str
    
    class Args(BaseModel):
        issue_key: str = Field(description="Issue key (e.g., PROJ-123)")
        comment: str = Field(description="Comment text")
    
    args_schema = Args
    
    async def _arun(
        self,
        issue_key: str,
        comment: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Add comment to Jira issue"""
        try:
            comment_data = {
                "body": {
                    "type": "doc",
                    "version": 1,
                    "content": [{
                        "type": "paragraph",
                        "content": [{
                            "type": "text",
                            "text": comment
                        }]
                    }]
                }
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.atlassian.com/ex/jira/{self.cloud_id}/rest/api/3/issue/{issue_key}/comment",
                    json=comment_data,
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Accept": "application/json",
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code in [200, 201]:
                    return f"Successfully added comment to issue: {issue_key}"
                elif response.status_code == 404:
                    return f"Issue not found: {issue_key}"
                else:
                    return f"Error adding comment: {response.status_code} - {response.text}"
                    
        except Exception as e:
            logger.error("Failed to add comment to Jira issue", error=str(e), exc_info=True)
            return f"Error adding comment: {str(e)}"
    
    def _run(self, *args, **kwargs):
        """Sync execution not supported"""
        raise NotImplementedError("Use async execution")


class ConfluenceSearchTool(BaseTool):
    """Tool for searching Confluence content using REST API"""
    
    name: str = "confluence_search"
    description: str = "Search for content in Confluence"
    
    access_token: str
    cloud_id: str
    
    class Args(BaseModel):
        query: str = Field(description="Search query")
        space: Optional[str] = Field(default=None, description="Limit to specific space")
        type: Optional[str] = Field(default=None, description="Content type filter (page, blogpost, etc.)")
        max_results: int = Field(default=10, description="Maximum number of results")
    
    args_schema = Args
    
    async def _arun(
        self,
        query: str,
        space: Optional[str] = None,
        type: Optional[str] = None,
        max_results: int = 10,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Execute Confluence search"""
        try:
            # Build CQL query
            cql = f'text ~ "{query}"'
            if space:
                cql += f' AND space = "{space}"'
            if type:
                cql += f' AND type = "{type}"'
            
            # Debug logging
            logger.info(
                "Confluence search request",
                cloud_id=self.cloud_id,
                cql=cql,
                has_token=bool(self.access_token),
                token_preview=self.access_token[:20] if self.access_token else None
            )
            
            async with httpx.AsyncClient() as client:
                # For OAuth 2.0 (3LO), we must use api.atlassian.com with cloud_id
                # According to Atlassian docs, OAuth uses /rest/api without /wiki prefix
                url = f"https://api.atlassian.com/ex/confluence/{self.cloud_id}/rest/api/search"
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Accept": "application/json"
                }
                params = {
                    "cql": cql,
                    "limit": max_results
                }
                
                logger.debug(
                    "Making Confluence API request",
                    url=url,
                    params=params,
                    headers_keys=list(headers.keys())
                )
                
                response = await client.get(url, params=params, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])
                    
                    if not results:
                        return "No content found matching your query."
                    
                    # Log the first result to understand structure
                    if results:
                        logger.info(
                            "Confluence search result structure",
                            first_result_keys=list(results[0].keys()) if results else [],
                            first_result_sample=str(results[0])[:1000] if results else None,
                            content_id=results[0].get("content", {}).get("id") if results[0].get("content") else results[0].get("id")
                        )
                    
                    # Format the results - handle different response structures
                    formatted_results = []
                    for item in results:
                        # Search API may return content wrapped in a "content" object
                        # or directly as top-level fields
                        content = item.get("content", item)
                        
                        # Extract the actual page ID - it might be nested
                        page_id = content.get("id", "unknown")
                        
                        # Log the actual ID being extracted
                        logger.info(
                            "Extracting page info from search result",
                            raw_id=item.get("id"),
                            content_id=item.get("content", {}).get("id"),
                            final_id=page_id,
                            title=content.get("title", "Untitled")
                        )
                        
                        result_data = {
                            "id": page_id,
                            "title": content.get("title", "Untitled"),
                            "type": content.get("type", "Unknown"),
                            "space": item.get("space", {}).get("name") or content.get("space", {}).get("name", "Unknown"),
                            "url": item.get("url") or item.get("_links", {}).get("webui", "") or content.get("_links", {}).get("webui", "")
                        }
                        formatted_results.append(result_data)
                    
                    return json.dumps(formatted_results, indent=2)
                elif response.status_code == 401:
                    logger.error(
                        "Confluence authentication failed",
                        status_code=response.status_code,
                        response_text=response.text[:500],
                        response_headers={k: v for k, v in response.headers.items() if k.lower() in ['www-authenticate', 'x-failure-category']}
                    )
                    return "Authentication failed. The access token may be invalid or lack the required Confluence scopes."
                elif response.status_code == 403:
                    return "Permission denied. You don't have access to search Confluence content."
                else:
                    logger.error(
                        "Confluence search error",
                        status_code=response.status_code,
                        response_text=response.text[:500]
                    )
                    return f"Error searching Confluence: {response.status_code} - {response.text}"
                    
        except Exception as e:
            logger.error("Confluence search failed", error=str(e), exc_info=True)
            return f"Error searching Confluence: {str(e)}"
    
    def _run(self, *args, **kwargs):
        """Sync execution not supported"""
        raise NotImplementedError("Use async execution")


class ConfluenceGetPageTool(BaseTool):
    """Tool for retrieving Confluence page content using REST API"""
    
    name: str = "confluence_get_page"
    description: str = "Get content of a specific Confluence page"
    
    access_token: str
    cloud_id: str
    
    class Args(BaseModel):
        page_id: str = Field(description="Page ID")
        expand: List[str] = Field(
            default_factory=lambda: ["body.storage", "version"],
            description="Additional data to expand"
        )
    
    args_schema = Args
    
    async def _arun(
        self,
        page_id: str,
        expand: List[str] = None,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Get Confluence page content"""
        try:
            # Use v2 API - v1 /rest/api/content has been deprecated and returns 410 Gone
            # v2 API uses /wiki/api/v2/pages/{id} format
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.atlassian.com/ex/confluence/{self.cloud_id}/wiki/api/v2/pages/{page_id}",
                    params={
                        "body-format": "storage",  # Get the storage format for raw content
                    },
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Accept": "application/json"
                    }
                )
                
                logger.info(
                    "Confluence v2 API get page response",
                    status_code=response.status_code,
                    page_id=page_id,
                    cloud_id=self.cloud_id,
                    url=f"https://api.atlassian.com/ex/confluence/{self.cloud_id}/wiki/api/v2/pages/{page_id}"
                )
                
                if response.status_code == 200:
                    page = response.json()
                    
                    # v2 API has different structure
                    # Extract body content - v2 returns body in a different format
                    body_content = ""
                    if "body" in page:
                        body = page["body"]
                        if "storage" in body:
                            body_content = body["storage"].get("value", "")
                        elif "view" in body:
                            body_content = body["view"].get("value", "")
                    
                    # Build result matching expected structure
                    result = {
                        "id": page.get("id", page_id),
                        "title": page.get("title", "Untitled"),
                        "type": page.get("type", "page"),
                        "space": page.get("spaceId", "Unknown"),  # v2 uses spaceId
                        "version": page.get("version", {}).get("number", 0),
                        "content": body_content,
                        "url": page.get("_links", {}).get("webui", f"/wiki/spaces/{page.get('spaceId')}/pages/{page_id}")
                    }
                    
                    return json.dumps(result, indent=2)
                elif response.status_code == 404:
                    return f"Page not found: {page_id}"
                elif response.status_code == 401:
                    logger.error(
                        "Confluence authentication failed",
                        status_code=response.status_code,
                        response_text=response.text[:500],
                        page_id=page_id
                    )
                    return "Authentication failed. The access token may be invalid or you don't have permission to view this page."
                elif response.status_code == 403:
                    return "Permission denied. You don't have access to view this page."
                else:
                    return f"Error getting page: {response.status_code} - {response.text}"
                    
        except Exception as e:
            logger.error("Failed to get Confluence page", error=str(e), exc_info=True)
            return f"Error getting page: {str(e)}"
    
    def _run(self, *args, **kwargs):
        """Sync execution not supported"""
        raise NotImplementedError("Use async execution")


class ConfluenceCreatePageTool(BaseTool):
    """Tool for creating a new Confluence page"""
    
    name: str = "confluence_create_page"
    description: str = "Create a new page in Confluence"
    
    access_token: str
    cloud_id: str
    
    class Args(BaseModel):
        title: str = Field(description="Page title")
        space_key: str = Field(description="Space key")
        content: str = Field(description="Page content (HTML format)")
        parent_id: Optional[str] = Field(default=None, description="Parent page ID (optional)")
    
    args_schema = Args
    
    async def _arun(
        self,
        title: str,
        space_key: str,
        content: str,
        parent_id: Optional[str] = None,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Create Confluence page"""
        try:
            page_data = {
                "type": "page",
                "title": title,
                "space": {"key": space_key},
                "body": {
                    "storage": {
                        "value": content,
                        "representation": "storage"
                    }
                }
            }
            
            if parent_id:
                page_data["ancestors"] = [{"id": parent_id}]
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.atlassian.com/ex/confluence/{self.cloud_id}/rest/api/content",
                    json=page_data,
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Accept": "application/json",
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code in [200, 201]:
                    page = response.json()
                    return f"Successfully created page: {page['id']} - {title}"
                else:
                    return f"Error creating page: {response.status_code} - {response.text}"
                    
        except Exception as e:
            logger.error("Failed to create Confluence page", error=str(e), exc_info=True)
            return f"Error creating page: {str(e)}"
    
    def _run(self, *args, **kwargs):
        """Sync execution not supported"""
        raise NotImplementedError("Use async execution")


class ConfluenceUpdatePageTool(BaseTool):
    """Tool for updating an existing Confluence page"""
    
    name: str = "confluence_update_page"
    description: str = "Update an existing Confluence page"
    
    access_token: str
    cloud_id: str
    
    class Args(BaseModel):
        page_id: str = Field(description="Page ID")
        title: Optional[str] = Field(default=None, description="New title (optional)")
        content: str = Field(description="New content")
        version_comment: Optional[str] = Field(default=None, description="Version comment")
    
    args_schema = Args
    
    async def _arun(
        self,
        page_id: str,
        content: str,
        title: Optional[str] = None,
        version_comment: Optional[str] = None,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Update Confluence page"""
        try:
            # First get the current page to get version number
            async with httpx.AsyncClient() as client:
                get_response = await client.get(
                    f"https://api.atlassian.com/ex/confluence/{self.cloud_id}/rest/api/content/{page_id}",
                    params={"expand": "version"},
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Accept": "application/json"
                    }
                )
                
                if get_response.status_code != 200:
                    return f"Error getting page: {get_response.status_code} - {get_response.text}"
                
                current_page = get_response.json()
                current_version = current_page["version"]["number"]
                
                # Prepare update data
                update_data = {
                    "type": "page",
                    "title": title or current_page["title"],
                    "body": {
                        "storage": {
                            "value": content,
                            "representation": "storage"
                        }
                    },
                    "version": {
                        "number": current_version + 1
                    }
                }
                
                if version_comment:
                    update_data["version"]["message"] = version_comment
                
                # Update the page
                update_response = await client.put(
                    f"https://api.atlassian.com/ex/confluence/{self.cloud_id}/rest/api/content/{page_id}",
                    json=update_data,
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Accept": "application/json",
                        "Content-Type": "application/json"
                    }
                )
                
                if update_response.status_code in [200, 201]:
                    return f"Successfully updated page: {page_id}"
                else:
                    return f"Error updating page: {update_response.status_code} - {update_response.text}"
                    
        except Exception as e:
            logger.error("Failed to update Confluence page", error=str(e), exc_info=True)
            return f"Error updating page: {str(e)}"
    
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
                    # Log all resources for debugging
                    for resource in resources:
                        logger.info(
                            "Atlassian resource found",
                            cloud_id=resource.get("id"),
                            site_name=resource.get("name"),
                            site_url=resource.get("url"),
                            scopes=resource.get("scopes", [])
                        )
                    
                    # Return the first cloud ID that has Confluence scopes
                    for resource in resources:
                        scopes = resource.get("scopes", [])
                        if any("confluence" in scope.lower() for scope in scopes):
                            cloud_id = resource.get("id")
                            logger.info(
                                "Using Atlassian Cloud ID with Confluence access",
                                cloud_id=cloud_id,
                                site_name=resource.get("name"),
                                site_url=resource.get("url"),
                                confluence_scopes=[s for s in scopes if "confluence" in s.lower()]
                            )
                            return cloud_id
                    
                    # If no Confluence scopes found, return first resource (for Jira)
                    cloud_id = resources[0].get("id")
                    logger.info(
                        "Using Atlassian Cloud ID (no Confluence scopes found)",
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
    
    # Get Cloud ID and site info
    cloud_id = await get_atlassian_cloud_id(access_token)
    if not cloud_id:
        logger.error("Could not get Atlassian Cloud ID")
        return []
    
    # For debugging - let's check what accessible-resources actually returns
    logger.info(
        "Creating Atlassian tools",
        cloud_id=cloud_id,
        tool_ids=tool_ids
    )
    
    # Create requested tools
    tool_map = {
        # Jira tools
        "jira_search_issues": JiraSearchTool,
        "jira_create_issue": CreateJiraIssueTool,
        "jira_get_issue": JiraGetIssueTool,
        "jira_update_issue": JiraUpdateIssueTool,
        "jira_add_comment": JiraAddCommentTool,
        # Confluence tools
        "confluence_search": ConfluenceSearchTool,
        "confluence_get_page": ConfluenceGetPageTool,
        "confluence_create_page": ConfluenceCreatePageTool,
        "confluence_update_page": ConfluenceUpdatePageTool,
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