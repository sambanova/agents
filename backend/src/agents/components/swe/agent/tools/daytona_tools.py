"""
SWE-specific Daytona tools that include Git operations and file management.
Follows the datagen pattern for proper sandbox integration.
"""

import os
import structlog
from typing import List, Optional, Dict, Any
from langchain.tools import tool
from pydantic import BaseModel, Field
from typing_extensions import Annotated
from agents.components.datagen.tools.persistent_daytona import PersistentDaytonaManager

logger = structlog.get_logger(__name__)


def get_swe_daytona_tools(manager: PersistentDaytonaManager) -> List:
    """
    Get SWE-specific Daytona tools that include Git operations and file management.
    
    Args:
        manager: PersistentDaytonaManager instance
        
    Returns:
        List of Daytona tools for SWE operations
    """
    if not manager:
        logger.warning("No Daytona manager provided, SWE Daytona tools will be disabled")
        return []

    @tool
    async def daytona_git_clone(
        url: Annotated[str, "Git repository URL to clone"],
        path: Annotated[str, "Path where to clone the repository (relative to sandbox root)"],
        branch: Annotated[str, "Branch to clone (default: main)"] = "main",
        username: Annotated[str, "Username for authentication (optional)"] = "",
        password: Annotated[str, "Password/token for authentication (optional)"] = "",
    ) -> str:
        """
        Clone a Git repository into the Daytona sandbox.
        This is the primary way to get repository code into the sandbox for analysis.
        """
        try:
            sandbox = await manager._get_sandbox()
            if not sandbox:
                return "Error: Daytona sandbox not initialized"
            
            logger.info(f"Cloning repository {url} to {path}")
            
            # Prepare clone parameters
            clone_params = {
                "url": url,
                "path": path,
                "branch": branch
            }
            
            # Add authentication if provided
            if username and password:
                clone_params["username"] = username
                clone_params["password"] = password
            
            # Clone the repository
            await sandbox.git.clone(**clone_params)
            
            logger.info(f"Successfully cloned {url} to {path}")
            return f"Successfully cloned repository {url} to {path} (branch: {branch})"
            
        except Exception as e:
            error_msg = f"Failed to clone repository {url}: {str(e)}"
            logger.error(error_msg)
            return error_msg

    @tool
    async def daytona_git_status(
        path: Annotated[str, "Path to the repository in the sandbox"]
    ) -> str:
        """
        Get the Git status of a repository in the sandbox.
        Returns current branch, modified files, and commit status.
        """
        try:
            sandbox = await manager._get_sandbox()
            if not sandbox:
                return "Error: Daytona sandbox not initialized"
            
            status = await sandbox.git.status(path)
            
            status_info = f"""Repository Status for {path}:
Current Branch: {status.current_branch}
Commits Ahead: {status.ahead}
Commits Behind: {status.behind}

Modified Files:"""
            
            if status.file_status:
                for file in status.file_status:
                    status_info += f"\n  - {file.name} ({file.status})"
            else:
                status_info += "\n  No modified files"
                
            return status_info
            
        except Exception as e:
            error_msg = f"Failed to get repository status for {path}: {str(e)}"
            logger.error(error_msg)
            return error_msg

    @tool
    async def daytona_git_branches(
        path: Annotated[str, "Path to the repository in the sandbox"]
    ) -> str:
        """
        List all branches in the repository.
        """
        try:
            sandbox = await manager._get_sandbox()
            if not sandbox:
                return "Error: Daytona sandbox not initialized"
            
            response = await sandbox.git.branches(path)
            
            branches_info = f"Branches in {path}:\n"
            for branch in response.branches:
                branches_info += f"  - {branch}\n"
                
            return branches_info
            
        except Exception as e:
            error_msg = f"Failed to list branches for {path}: {str(e)}"
            logger.error(error_msg)
            return error_msg

    @tool
    async def daytona_git_checkout(
        path: Annotated[str, "Path to the repository in the sandbox"],
        branch: Annotated[str, "Branch name to checkout"]
    ) -> str:
        """
        Checkout a specific branch in the repository.
        """
        try:
            sandbox = await manager._get_sandbox()
            if not sandbox:
                return "Error: Daytona sandbox not initialized"
            
            await sandbox.git.checkout_branch(path, branch)
            return f"Successfully checked out branch '{branch}' in {path}"
            
        except Exception as e:
            error_msg = f"Failed to checkout branch {branch} in {path}: {str(e)}"
            logger.error(error_msg)
            return error_msg

    @tool
    async def daytona_git_create_branch(
        path: Annotated[str, "Path to the repository in the sandbox"],
        branch: Annotated[str, "Name of the new branch to create"]
    ) -> str:
        """
        Create a new branch in the repository.
        """
        try:
            sandbox = await manager._get_sandbox()
            if not sandbox:
                return "Error: Daytona sandbox not initialized"
            
            await sandbox.git.create_branch(path, branch)
            return f"Successfully created branch '{branch}' in {path}"
            
        except Exception as e:
            error_msg = f"Failed to create branch {branch} in {path}: {str(e)}"
            logger.error(error_msg)
            return error_msg

    @tool
    async def daytona_git_add(
        path: Annotated[str, "Path to the repository in the sandbox"],
        files: Annotated[List[str], "List of files to stage (use ['.'] for all files)"]
    ) -> str:
        """
        Stage files for commit in the repository.
        """
        try:
            sandbox = await manager._get_sandbox()
            if not sandbox:
                return "Error: Daytona sandbox not initialized"
            
            await sandbox.git.add(path, files)
            return f"Successfully staged files in {path}: {', '.join(files)}"
            
        except Exception as e:
            error_msg = f"Failed to stage files in {path}: {str(e)}"
            logger.error(error_msg)
            return error_msg

    @tool
    async def daytona_git_commit(
        path: Annotated[str, "Path to the repository in the sandbox"],
        message: Annotated[str, "Commit message"],
        author_name: Annotated[str, "Author name for the commit"],
        author_email: Annotated[str, "Author email for the commit"]
    ) -> str:
        """
        Commit staged changes in the repository.
        """
        try:
            sandbox = await manager._get_sandbox()
            if not sandbox:
                return "Error: Daytona sandbox not initialized"
            
            await sandbox.git.commit(path, message, author_name, author_email)
            return f"Successfully committed changes in {path} with message: '{message}'"
            
        except Exception as e:
            error_msg = f"Failed to commit changes in {path}: {str(e)}"
            logger.error(error_msg)
            return error_msg

    @tool
    async def daytona_list_files(
        directory: Annotated[str, "Directory to list files from"] = "."
    ) -> str:
        """
        List files in the Daytona sandbox directory.
        Use this to explore the repository structure after cloning.
        """
        try:
            files = await manager.list_files(directory)
            if isinstance(files, list):
                return f"Files in {directory}:\n" + "\n".join(files)
            else:
                return files  # Already a formatted string
                
        except Exception as e:
            error_msg = f"Failed to list files in {directory}: {str(e)}"
            logger.error(error_msg)
            return error_msg

    @tool
    async def daytona_read_file(
        filename: Annotated[str, "Path to the file to read from the sandbox"]
    ) -> str:
        """
        Read a file from the Daytona sandbox.
        Use this to analyze code files after cloning the repository.
        """
        try:
            success, content = await manager.read_file(filename)
            if success:
                return f"Content of {filename}:\n\n{content}"
            else:
                return content  # Error message
                
        except Exception as e:
            error_msg = f"Failed to read file {filename}: {str(e)}"
            logger.error(error_msg)
            return error_msg

    @tool
    async def daytona_write_file(
        filename: Annotated[str, "Path to the file to write in the sandbox"],
        content: Annotated[str, "Content to write to the file"]
    ) -> str:
        """
        Write content to a file in the Daytona sandbox.
        Use this to create or modify files in the repository.
        """
        try:
            result = await manager.write_file(filename, content)
            return result
            
        except Exception as e:
            error_msg = f"Failed to write file {filename}: {str(e)}"
            logger.error(error_msg)
            return error_msg

    @tool
    async def daytona_execute_command(
        command: Annotated[str, "Shell command to execute in the sandbox"],
        timeout: Annotated[int, "Timeout in seconds (default: 60)"] = 60
    ) -> str:
        """
        Execute a shell command in the Daytona sandbox.
        Use this for any command-line operations like running tests, builds, etc.
        """
        try:
            result = await manager.execute(command, timeout)
            return result
            
        except Exception as e:
            error_msg = f"Failed to execute command '{command}': {str(e)}"
            logger.error(error_msg)
            return error_msg

    @tool
    async def daytona_get_repository_structure(
        directory: Annotated[str, "Repository directory to analyze"] = "."
    ) -> str:
        """
        Get a comprehensive view of the repository structure including files and directories.
        This provides a tree-like view of the codebase for analysis.
        """
        try:
            # Use the existing get_all_files_recursive method
            all_files = await manager.get_all_files_recursive(directory)
            
            if not all_files:
                return f"No files found in directory {directory}"
            
            # Group files by directory
            structure = {}
            for file_info in all_files:
                file_path = file_info["path"]
                dir_path = os.path.dirname(file_path) if "/" in file_path else "."
                
                if dir_path not in structure:
                    structure[dir_path] = []
                structure[dir_path].append(os.path.basename(file_path))
            
            # Format the structure
            result = f"Repository structure for {directory}:\n"
            for dir_path in sorted(structure.keys()):
                result += f"\n{dir_path}/\n"
                for file_name in sorted(structure[dir_path]):
                    result += f"  - {file_name}\n"
            
            return result
            
        except Exception as e:
            error_msg = f"Failed to get repository structure for {directory}: {str(e)}"
            logger.error(error_msg)
            return error_msg

    return [
        daytona_git_clone,
        daytona_git_status,
        daytona_git_branches,
        daytona_git_checkout,
        daytona_git_create_branch,
        daytona_git_add,
        daytona_git_commit,
        daytona_list_files,
        daytona_read_file,
        daytona_write_file,
        daytona_execute_command,
        daytona_get_repository_structure,
    ]


# Tool names for easy reference
SWE_DAYTONA_TOOL_NAMES = [
    "daytona_git_clone",
    "daytona_git_status",
    "daytona_git_branches",
    "daytona_git_checkout",
    "daytona_git_create_branch",
    "daytona_git_add",
    "daytona_git_commit",
    "daytona_list_files",
    "daytona_read_file",
    "daytona_write_file",
    "daytona_execute_command",
    "daytona_get_repository_structure",
] 