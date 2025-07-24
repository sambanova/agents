"""
Repository manager for SWE agents - handles repository context and operations.
"""
import os
import tempfile
import shutil
from typing import Dict, Any, Optional, List
from pathlib import Path
import structlog
from agents.components.swe.agent.tools.github_tools import GitHubManager

logger = structlog.get_logger(__name__)


class RepositoryContext:
    """Represents the context of a repository for SWE operations."""
    
    def __init__(
        self,
        repo_full_name: str,
        branch: str = "main",
        github_token: str = None,
        local_path: str = None,
        daytona_manager = None,
    ):
        self.repo_full_name = repo_full_name  # e.g., "owner/repo"
        self.branch = branch
        self.github_token = github_token
        self.local_path = local_path
        self.daytona_manager = daytona_manager
        self.github_manager = GitHubManager(github_token) if github_token else None
        
        # Parse owner and repo name
        if "/" in repo_full_name:
            self.owner, self.repo_name = repo_full_name.split("/", 1)
        else:
            raise ValueError("Repository full name must be in format 'owner/repo'")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert repository context to dictionary."""
        return {
            "repo_full_name": self.repo_full_name,
            "owner": self.owner,
            "repo_name": self.repo_name,
            "branch": self.branch,
            "local_path": self.local_path,
            "has_github_token": bool(self.github_token),
        }
    
    async def get_repo_info(self) -> Dict[str, Any]:
        """Get repository information from GitHub."""
        if not self.github_manager:
            return {}
        
        try:
            return await self.github_manager.get_repo_info(self.owner, self.repo_name)
        except Exception as e:
            logger.error(f"Failed to get repo info: {str(e)}")
            return {}
    
    async def get_file_structure(self, path: str = "") -> List[Dict[str, Any]]:
        """Get repository file structure."""
        if not self.github_manager:
            return []
        
        try:
            return await self.github_manager.get_repo_contents(self.owner, self.repo_name, path)
        except Exception as e:
            logger.error(f"Failed to get file structure: {str(e)}")
            return []
    
    async def get_file_content(self, file_path: str) -> str:
        """Get content of a specific file."""
        if not self.github_manager:
            return ""
        
        try:
            return await self.github_manager.get_file_content(self.owner, self.repo_name, file_path)
        except Exception as e:
            logger.error(f"Failed to get file content: {str(e)}")
            return ""
    
    async def clone_to_daytona(self) -> bool:
        """Clone repository to Daytona workspace."""
        if not self.daytona_manager:
            logger.warning("No Daytona manager provided")
            return False
        
        try:
            # Get repository info
            repo_info = await self.get_repo_info()
            if not repo_info:
                logger.error("Could not get repository info")
                return False
            
            clone_url = repo_info.get("clone_url", f"https://github.com/{self.repo_full_name}.git")
            
            # Create clone command
            clone_command = f"git clone {clone_url} {self.repo_name}"
            if self.branch != "main":
                clone_command += f" -b {self.branch}"
            
            # Execute clone in Daytona
            result = await self.daytona_manager.execute(clone_command, timeout=300)
            
            if "Cloning into" in result or "already exists" in result:
                logger.info(f"Successfully cloned {self.repo_full_name} to Daytona")
                return True
            else:
                logger.error(f"Failed to clone repository: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Error cloning repository to Daytona: {str(e)}")
            return False


class RepositoryManager:
    """Manages repository operations for SWE agents."""
    
    def __init__(self, github_token: str = None, daytona_manager = None):
        self.github_token = github_token
        self.daytona_manager = daytona_manager
        self.github_manager = GitHubManager(github_token) if github_token else None
        self.current_context: Optional[RepositoryContext] = None
    
    async def list_user_repositories(self) -> List[Dict[str, Any]]:
        """List repositories for the authenticated user."""
        if not self.github_manager:
            return []
        
        try:
            repos = await self.github_manager.get_user_repos()
            return [
                {
                    "name": repo["name"],
                    "full_name": repo["full_name"],
                    "description": repo.get("description", ""),
                    "language": repo.get("language", "Unknown"),
                    "updated_at": repo["updated_at"],
                    "private": repo["private"],
                    "default_branch": repo["default_branch"],
                }
                for repo in repos
            ]
        except Exception as e:
            logger.error(f"Failed to list user repositories: {str(e)}")
            return []
    
    async def validate_repository(self, repo_full_name: str) -> Dict[str, Any]:
        """Validate if a repository exists and is accessible."""
        if not self.github_manager:
            return {"valid": False, "error": "No GitHub token provided"}
        
        try:
            if "/" not in repo_full_name:
                return {"valid": False, "error": "Invalid repository format. Use 'owner/repo'"}
            
            owner, repo = repo_full_name.split("/", 1)
            repo_info = await self.github_manager.get_repo_info(owner, repo)
            
            if repo_info:
                return {
                    "valid": True,
                    "repo_info": {
                        "name": repo_info["name"],
                        "full_name": repo_info["full_name"],
                        "description": repo_info.get("description", ""),
                        "language": repo_info.get("language", "Unknown"),
                        "default_branch": repo_info["default_branch"],
                        "private": repo_info["private"],
                    }
                }
            else:
                return {"valid": False, "error": "Repository not found or access denied"}
                
        except Exception as e:
            logger.error(f"Error validating repository: {str(e)}")
            return {"valid": False, "error": f"Validation failed: {str(e)}"}
    
    async def set_repository_context(
        self, 
        repo_full_name: str, 
        branch: str = "main",
        clone_to_daytona: bool = True
    ) -> bool:
        """Set the current repository context for SWE operations."""
        try:
            # Validate repository first
            validation = await self.validate_repository(repo_full_name)
            if not validation["valid"]:
                logger.error(f"Repository validation failed: {validation['error']}")
                return False
            
            # Create repository context
            self.current_context = RepositoryContext(
                repo_full_name=repo_full_name,
                branch=branch,
                github_token=self.github_token,
                daytona_manager=self.daytona_manager,
            )
            
            # Clone to Daytona if requested
            if clone_to_daytona and self.daytona_manager:
                success = await self.current_context.clone_to_daytona()
                if not success:
                    logger.warning("Failed to clone repository to Daytona, but context is set")
            
            logger.info(f"Repository context set: {repo_full_name} (branch: {branch})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set repository context: {str(e)}")
            return False
    
    def get_current_context(self) -> Optional[RepositoryContext]:
        """Get the current repository context."""
        return self.current_context
    
    def clear_context(self):
        """Clear the current repository context."""
        self.current_context = None
        logger.info("Repository context cleared")


def get_repository_selection_schema() -> Dict[str, Any]:
    """
    Get the schema for repository selection that can be used by the frontend.
    This defines the structure for repository selection UI components.
    """
    return {
        "type": "object",
        "properties": {
            "selection_type": {
                "type": "string",
                "enum": ["user_repo", "public_repo"],
                "description": "Whether to select from user's repositories or enter a public repo"
            },
            "repo_full_name": {
                "type": "string",
                "pattern": r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$",
                "description": "Full repository name in format 'owner/repo'"
            },
            "branch": {
                "type": "string",
                "default": "main",
                "description": "Branch to work with"
            },
            "clone_to_workspace": {
                "type": "boolean",
                "default": True,
                "description": "Whether to clone the repository to the workspace"
            }
        },
        "required": ["selection_type", "repo_full_name"],
        "additionalProperties": False
    }


# API endpoint schemas for frontend integration
REPOSITORY_API_SCHEMAS = {
    "list_user_repos": {
        "method": "GET",
        "endpoint": "/api/swe/repositories/user",
        "description": "List repositories for the authenticated user",
        "requires_auth": True,
        "response_schema": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "full_name": {"type": "string"},
                    "description": {"type": "string"},
                    "language": {"type": "string"},
                    "updated_at": {"type": "string"},
                    "private": {"type": "boolean"},
                    "default_branch": {"type": "string"}
                }
            }
        }
    },
    "validate_repository": {
        "method": "POST",
        "endpoint": "/api/swe/repositories/validate",
        "description": "Validate if a repository exists and is accessible",
        "requires_auth": True,
        "request_schema": {
            "type": "object",
            "properties": {
                "repo_full_name": {"type": "string"}
            },
            "required": ["repo_full_name"]
        },
        "response_schema": {
            "type": "object",
            "properties": {
                "valid": {"type": "boolean"},
                "error": {"type": "string"},
                "repo_info": {"type": "object"}
            }
        }
    },
    "set_repository_context": {
        "method": "POST",
        "endpoint": "/api/swe/repositories/context",
        "description": "Set repository context for SWE operations",
        "requires_auth": True,
        "request_schema": get_repository_selection_schema(),
        "response_schema": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "message": {"type": "string"},
                "context": {"type": "object"}
            }
        }
    }
} 