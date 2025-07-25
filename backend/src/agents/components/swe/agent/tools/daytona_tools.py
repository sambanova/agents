"""
SWE-specific Daytona tools that include Git operations and file management.
Follows the datagen pattern for proper sandbox integration.
"""

import os
import re
import json
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
            try:
                await sandbox.git.clone(**clone_params)
                logger.info(f"Successfully cloned {url} to {path}")
                return f"Successfully cloned repository {url} to {path} (branch: {branch})"
            except Exception as clone_error:
                # Check if it's a "repository already exists" error
                if "already exists" in str(clone_error).lower():
                    logger.info(f"Repository {path} already exists, skipping clone")
                    return f"Repository {url} already exists at {path}, using existing repository"
                else:
                    # Re-raise other clone errors
                    raise clone_error
            
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
                    # Handle both file.status and direct string representation
                    file_status = getattr(file, 'status', str(file))
                    status_info += f"\n  - {file.name} ({file_status})"
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
    async def daytona_git_push(
        path: Annotated[str, "Path to the repository in the sandbox"]
    ) -> str:
        """
        Push commits to the remote repository.
        """
        try:
            sandbox = await manager._get_sandbox()
            if not sandbox:
                return "Error: Daytona sandbox not initialized"
            
            await sandbox.git.push(path)
            return f"Successfully pushed changes in {path} to remote repository"
            
        except Exception as e:
            error_msg = f"Failed to push changes in {path}: {str(e)}"
            logger.error(error_msg)
            return error_msg

    @tool
    async def daytona_git_pull(
        path: Annotated[str, "Path to the repository in the sandbox"]
    ) -> str:
        """
        Pull latest changes from the remote repository.
        """
        try:
            sandbox = await manager._get_sandbox()
            if not sandbox:
                return "Error: Daytona sandbox not initialized"
            
            await sandbox.git.pull(path)
            return f"Successfully pulled latest changes in {path} from remote repository"
            
        except Exception as e:
            error_msg = f"Failed to pull changes in {path}: {str(e)}"
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

    @tool
    async def daytona_search_keyword_in_directory(
        directory: Annotated[str, "Directory to search in within the sandbox"],
        search_term: Annotated[str, "Term to search for in files (case-insensitive, minimum 3 characters)"],
        context: Annotated[int, "Number of context lines before and after each match"] = 2
    ) -> str:
        """
        Search for a keyword in all files within a directory in the Daytona sandbox.
        This is like Cmd+F in your IDE but works within the sandbox environment.
        """
        try:
            if len(search_term) < 3:
                return "Error: search_term must be at least 3 characters long"
            
            # Get all files in the directory recursively
            all_files = await manager.get_all_files_recursive(directory)
            
            if not all_files:
                return f"No files found in directory {directory}"
            
            results = []
            pattern = re.compile(re.escape(search_term), re.IGNORECASE)
            
            for file_info in all_files:
                file_path = file_info["path"]
                
                # Skip binary files and only search text files
                if not any(file_path.endswith(ext) for ext in ['.py', '.js', '.jsx', '.ts', '.tsx', '.vue', '.html', '.css', '.json', '.md', '.txt', '.yml', '.yaml']):
                    continue
                
                try:
                    success, content = await manager.read_file(file_path)
                    if not success:
                        continue
                    
                    lines = content.splitlines()
                    
                    for i, line in enumerate(lines):
                        if pattern.search(line):
                            # Get context lines
                            start = max(i - context, 0)
                            end = min(i + context + 1, len(lines))
                            
                            results.append(f"\nFile: {file_path}")
                            results.append(f"Match found at line: {i + 1}")
                            
                            for j in range(start, end):
                                line_marker = ">>>" if j == i else "   "
                                results.append(f"{line_marker} {j+1:4} | {lines[j]}")
                            
                            results.append("-" * 50)
                            
                except Exception as e:
                    logger.warning(f"Could not search in file {file_path}: {e}")
                    continue
            
            if not results:
                return f"No matches found for '{search_term}' in {directory}"
            
            return "\n".join(results)
            
        except Exception as e:
            error_msg = f"Failed to search for '{search_term}' in {directory}: {str(e)}"
            logger.error(error_msg)
            return error_msg

    @tool
    async def daytona_get_code_definitions(
        file_path: Annotated[str, "Path to the source file to analyze in the sandbox"]
    ) -> str:
        """
        Extract function and class definitions from a file in the Daytona sandbox.
        Shows signatures with line numbers. Works with Python, JavaScript, TypeScript files.
        """
        try:
            # Read file from sandbox
            success, content = await manager.read_file(file_path)
            if not success:
                return content  # Error message
            
            # Simple regex-based parsing for common languages
            lines = content.splitlines()
            definitions = []
            
            # Determine file type
            suffix = file_path.split(".")[-1].lower()
            
            if suffix == "py":
                # Python definitions
                class_pattern = re.compile(r'^(\s*)class\s+(\w+).*?:')
                func_pattern = re.compile(r'^(\s*)def\s+(\w+)\s*\(.*?\):')
                
                for i, line in enumerate(lines):
                    class_match = class_pattern.match(line)
                    func_match = func_pattern.match(line)
                    
                    if class_match:
                        indent, name = class_match.groups()
                        definitions.append(f"{i+1:4} | {line.strip()}")
                    elif func_match:
                        indent, name = func_match.groups()
                        definitions.append(f"{i+1:4} | {line.strip()}")
                        
            elif suffix in ["js", "jsx", "ts", "tsx"]:
                # JavaScript/TypeScript definitions
                func_patterns = [
                    re.compile(r'^\s*function\s+(\w+)\s*\(.*?\)'),
                    re.compile(r'^\s*const\s+(\w+)\s*=\s*\(.*?\)\s*=>'),
                    re.compile(r'^\s*(\w+)\s*:\s*function\s*\(.*?\)'),
                    re.compile(r'^\s*(\w+)\s*\(.*?\)\s*\{'),  # Method definitions
                ]
                class_pattern = re.compile(r'^\s*class\s+(\w+)')
                
                for i, line in enumerate(lines):
                    class_match = class_pattern.match(line)
                    if class_match:
                        definitions.append(f"{i+1:4} | {line.strip()}")
                        continue
                    
                    for pattern in func_patterns:
                        if pattern.match(line):
                            definitions.append(f"{i+1:4} | {line.strip()}")
                            break
                            
            elif suffix == "vue":
                # Vue.js component methods
                func_pattern = re.compile(r'^\s*(\w+)\s*\(.*?\)\s*\{')
                setup_pattern = re.compile(r'^\s*setup\s*\(.*?\)')
                
                for i, line in enumerate(lines):
                    if func_pattern.match(line) or setup_pattern.match(line):
                        definitions.append(f"{i+1:4} | {line.strip()}")
            
            if not definitions:
                return f"No function or class definitions found in {file_path}"
            
            result = f"\nCode definitions in {file_path}:\n"
            result += "\n".join(definitions)
            return result
            
        except Exception as e:
            error_msg = f"Failed to get code definitions from {file_path}: {str(e)}"
            logger.error(error_msg)
            return error_msg

    @tool
    async def daytona_get_function_implementation(
        file_path: Annotated[str, "Path to the source file in the sandbox"],
        function_name: Annotated[str, "Name of the function to extract"]
    ) -> str:
        """
        Extract the full implementation of a specific function from a file in the Daytona sandbox.
        """
        try:
            # Read file from sandbox
            success, content = await manager.read_file(file_path)
            if not success:
                return content  # Error message
            
            lines = content.splitlines()
            
            # Simple function extraction (works for most cases)
            function_lines = []
            found_function = False
            initial_indent = None
            
            for i, line in enumerate(lines):
                # Look for function definition
                if (f"def {function_name}(" in line or 
                    f"function {function_name}(" in line or
                    f"const {function_name} =" in line or
                    f"{function_name}(" in line):
                    
                    found_function = True
                    initial_indent = len(line) - len(line.lstrip())
                    function_lines.append(f"{i+1:4} | {line}")
                    continue
                
                if found_function:
                    # Continue until we find a line with same or less indentation (or empty line)
                    current_indent = len(line) - len(line.lstrip()) if line.strip() else initial_indent + 1
                    
                    if line.strip() == "" or current_indent > initial_indent:
                        function_lines.append(f"{i+1:4} | {line}")
                    else:
                        # End of function
                        break
            
            if not function_lines:
                return f"Function '{function_name}' not found in {file_path}"
            
            result = f"\nFunction '{function_name}' implementation in {file_path}:\n"
            result += "\n".join(function_lines)
            return result
            
        except Exception as e:
            error_msg = f"Failed to get function implementation from {file_path}: {str(e)}"
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
        daytona_git_push,
        daytona_git_pull,
        daytona_list_files,
        daytona_read_file,
        daytona_write_file,
        daytona_execute_command,
        daytona_get_repository_structure,
        daytona_search_keyword_in_directory,
        daytona_get_code_definitions,
        daytona_get_function_implementation,
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
    "daytona_git_push",
    "daytona_git_pull",
    "daytona_list_files",
    "daytona_read_file",
    "daytona_write_file",
    "daytona_execute_command",
    "daytona_get_repository_structure",
    "daytona_search_keyword_in_directory",
    "daytona_get_code_definitions",
    "daytona_get_function_implementation",
] 