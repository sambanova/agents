"""
GitHub tools for SWE agents - provides repository operations using GitHub API.
"""
import os
import json
from typing import List, Optional, Dict, Any
from langchain.tools import tool
from pydantic import BaseModel, Field
from typing_extensions import Annotated
import httpx
import structlog

logger = structlog.get_logger(__name__)


class GitHubAPIError(Exception):
    """Custom exception for GitHub API errors."""
    pass


class GitHubManager:
    """Manages GitHub API operations using a Personal Access Token."""
    
    def __init__(self, github_token: str):
        self.github_token = github_token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "SWE-Agent/1.0"
        }
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[Any, Any]:
        """Make a request to the GitHub API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    timeout=30.0,
                    **kwargs
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"GitHub API error: {e.response.status_code} - {e.response.text}")
                raise GitHubAPIError(f"GitHub API error: {e.response.status_code}")
            except Exception as e:
                logger.error(f"Request error: {str(e)}")
                raise GitHubAPIError(f"Request failed: {str(e)}")
    
    async def get_user_repos(self, per_page: int = 30) -> List[Dict[str, Any]]:
        """Get repositories for the authenticated user."""
        try:
            repos = await self._make_request(
                "GET", 
                f"/user/repos?sort=updated&per_page={per_page}"
            )
            return repos
        except Exception as e:
            logger.error(f"Failed to get user repos: {str(e)}")
            return []
    
    async def get_repo_info(self, owner: str, repo: str) -> Dict[str, Any]:
        """Get information about a specific repository."""
        try:
            return await self._make_request("GET", f"/repos/{owner}/{repo}")
        except Exception as e:
            logger.error(f"Failed to get repo info for {owner}/{repo}: {str(e)}")
            return {}
    
    async def get_repo_contents(self, owner: str, repo: str, path: str = "") -> List[Dict[str, Any]]:
        """Get contents of a repository directory."""
        try:
            endpoint = f"/repos/{owner}/{repo}/contents"
            if path:
                endpoint += f"/{path}"
            return await self._make_request("GET", endpoint)
        except Exception as e:
            logger.error(f"Failed to get repo contents: {str(e)}")
            return []
    
    async def get_file_content(self, owner: str, repo: str, path: str) -> str:
        """Get the content of a specific file."""
        try:
            response = await self._make_request("GET", f"/repos/{owner}/{repo}/contents/{path}")
            if response.get("type") == "file":
                import base64
                content = base64.b64decode(response["content"]).decode("utf-8")
                return content
            return ""
        except Exception as e:
            logger.error(f"Failed to get file content: {str(e)}")
            return ""
    
    async def get_repo_branches(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        """Get branches for a repository."""
        try:
            return await self._make_request("GET", f"/repos/{owner}/{repo}/branches")
        except Exception as e:
            logger.error(f"Failed to get branches: {str(e)}")
            return []
    
    async def get_repo_issues(self, owner: str, repo: str, state: str = "open") -> List[Dict[str, Any]]:
        """Get issues for a repository."""
        try:
            return await self._make_request("GET", f"/repos/{owner}/{repo}/issues?state={state}")
        except Exception as e:
            logger.error(f"Failed to get issues: {str(e)}")
            return []
    
    async def get_repo_pulls(self, owner: str, repo: str, state: str = "open") -> List[Dict[str, Any]]:
        """Get pull requests for a repository."""
        try:
            return await self._make_request("GET", f"/repos/{owner}/{repo}/pulls?state={state}")
        except Exception as e:
            logger.error(f"Failed to get pull requests: {str(e)}")
            return []


def get_github_tools(github_token: str) -> List:
    """
    Get GitHub tools configured for SWE agents.

    Args:
        github_token: GitHub Personal Access Token

    Returns:
        List of GitHub tools for repository operations
    """
    if not github_token:
        logger.warning("No GitHub token provided, GitHub tools will be disabled")
        return []
    
    github_manager = GitHubManager(github_token)

    @tool
    async def github_list_user_repos() -> str:
        """
        List repositories for the authenticated GitHub user.
        Returns a list of repositories with basic information.
        """
        try:
            repos = await github_manager.get_user_repos()
            if not repos:
                return "No repositories found or failed to fetch repositories."
            
            repo_list = []
            for repo in repos[:20]:  # Limit to first 20 repos
                repo_info = {
                    "name": repo["name"],
                    "full_name": repo["full_name"],
                    "description": repo.get("description", "No description"),
                    "language": repo.get("language", "Unknown"),
                    "updated_at": repo["updated_at"],
                    "private": repo["private"]
                }
                repo_list.append(repo_info)
            
            return json.dumps(repo_list, indent=2)
        except Exception as e:
            return f"Error listing repositories: {str(e)}"

    @tool
    async def github_get_repo_info(
        repo_full_name: Annotated[str, "Full repository name (owner/repo)"]
    ) -> str:
        """
        Get detailed information about a specific GitHub repository.
        """
        try:
            if "/" not in repo_full_name:
                return "Invalid repository format. Use 'owner/repo' format."
            
            owner, repo = repo_full_name.split("/", 1)
            repo_info = await github_manager.get_repo_info(owner, repo)
            
            if not repo_info:
                return f"Repository {repo_full_name} not found or access denied."
            
            info = {
                "name": repo_info["name"],
                "full_name": repo_info["full_name"],
                "description": repo_info.get("description", "No description"),
                "language": repo_info.get("language", "Unknown"),
                "size": repo_info["size"],
                "default_branch": repo_info["default_branch"],
                "clone_url": repo_info["clone_url"],
                "ssh_url": repo_info["ssh_url"],
                "created_at": repo_info["created_at"],
                "updated_at": repo_info["updated_at"],
                "private": repo_info["private"],
                "topics": repo_info.get("topics", [])
            }
            
            return json.dumps(info, indent=2)
        except Exception as e:
            return f"Error getting repository info: {str(e)}"

    @tool
    async def github_list_repo_contents(
        repo_full_name: Annotated[str, "Full repository name (owner/repo)"],
        path: Annotated[str, "Path within the repository (empty for root)"] = ""
    ) -> str:
        """
        List contents of a directory in a GitHub repository.
        """
        try:
            if "/" not in repo_full_name:
                return "Invalid repository format. Use 'owner/repo' format."
            
            owner, repo = repo_full_name.split("/", 1)
            contents = await github_manager.get_repo_contents(owner, repo, path)
            
            if not contents:
                return f"No contents found at path '{path}' or access denied."
            
            items = []
            for item in contents:
                item_info = {
                    "name": item["name"],
                    "type": item["type"],
                    "size": item.get("size", 0),
                    "path": item["path"]
                }
                items.append(item_info)
            
            return json.dumps(items, indent=2)
        except Exception as e:
            return f"Error listing repository contents: {str(e)}"

    @tool
    async def github_get_file_content(
        repo_full_name: Annotated[str, "Full repository name (owner/repo)"],
        file_path: Annotated[str, "Path to the file within the repository"]
    ) -> str:
        """
        Get the content of a specific file from a GitHub repository.
        """
        try:
            if "/" not in repo_full_name:
                return "Invalid repository format. Use 'owner/repo' format."
            
            owner, repo = repo_full_name.split("/", 1)
            content = await github_manager.get_file_content(owner, repo, file_path)
            
            if not content:
                return f"File '{file_path}' not found or empty."
            
            return f"Content of {file_path}:\n\n{content}"
        except Exception as e:
            return f"Error getting file content: {str(e)}"

    @tool
    async def github_list_branches(
        repo_full_name: Annotated[str, "Full repository name (owner/repo)"]
    ) -> str:
        """
        List branches for a GitHub repository.
        """
        try:
            if "/" not in repo_full_name:
                return "Invalid repository format. Use 'owner/repo' format."
            
            owner, repo = repo_full_name.split("/", 1)
            branches = await github_manager.get_repo_branches(owner, repo)
            
            if not branches:
                return "No branches found or access denied."
            
            branch_list = []
            for branch in branches:
                branch_info = {
                    "name": branch["name"],
                    "protected": branch.get("protected", False),
                    "commit_sha": branch["commit"]["sha"]
                }
                branch_list.append(branch_info)
            
            return json.dumps(branch_list, indent=2)
        except Exception as e:
            return f"Error listing branches: {str(e)}"

    @tool
    async def github_list_issues(
        repo_full_name: Annotated[str, "Full repository name (owner/repo)"],
        state: Annotated[str, "Issue state: open, closed, or all"] = "open"
    ) -> str:
        """
        List issues for a GitHub repository.
        """
        try:
            if "/" not in repo_full_name:
                return "Invalid repository format. Use 'owner/repo' format."
            
            owner, repo = repo_full_name.split("/", 1)
            issues = await github_manager.get_repo_issues(owner, repo, state)
            
            if not issues:
                return f"No {state} issues found."
            
            issue_list = []
            for issue in issues[:20]:  # Limit to first 20 issues
                issue_info = {
                    "number": issue["number"],
                    "title": issue["title"],
                    "state": issue["state"],
                    "author": issue["user"]["login"],
                    "created_at": issue["created_at"],
                    "updated_at": issue["updated_at"],
                    "labels": [label["name"] for label in issue.get("labels", [])],
                    "assignees": [assignee["login"] for assignee in issue.get("assignees", [])]
                }
                issue_list.append(issue_info)
            
            return json.dumps(issue_list, indent=2)
        except Exception as e:
            return f"Error listing issues: {str(e)}"

    @tool
    async def github_list_pull_requests(
        repo_full_name: Annotated[str, "Full repository name (owner/repo)"],
        state: Annotated[str, "PR state: open, closed, or all"] = "open"
    ) -> str:
        """
        List pull requests for a GitHub repository.
        """
        try:
            if "/" not in repo_full_name:
                return "Invalid repository format. Use 'owner/repo' format."
            
            owner, repo = repo_full_name.split("/", 1)
            pulls = await github_manager.get_repo_pulls(owner, repo, state)
            
            if not pulls:
                return f"No {state} pull requests found."
            
            pr_list = []
            for pr in pulls[:20]:  # Limit to first 20 PRs
                pr_info = {
                    "number": pr["number"],
                    "title": pr["title"],
                    "state": pr["state"],
                    "author": pr["user"]["login"],
                    "created_at": pr["created_at"],
                    "updated_at": pr["updated_at"],
                    "base_branch": pr["base"]["ref"],
                    "head_branch": pr["head"]["ref"],
                    "draft": pr.get("draft", False)
                }
                pr_list.append(pr_info)
            
            return json.dumps(pr_list, indent=2)
        except Exception as e:
            return f"Error listing pull requests: {str(e)}"

    return [
        github_list_user_repos,
        github_get_repo_info,
        github_list_repo_contents,
        github_get_file_content,
        github_list_branches,
        github_list_issues,
        github_list_pull_requests,
    ]


# Tool names for easy reference
GITHUB_TOOL_NAMES = [
    "github_list_user_repos",
    "github_get_repo_info", 
    "github_list_repo_contents",
    "github_get_file_content",
    "github_list_branches",
    "github_list_issues",
    "github_list_pull_requests",
] 