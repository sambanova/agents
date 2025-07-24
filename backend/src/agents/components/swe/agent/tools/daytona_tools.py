"""
Daytona tools for SWE agents - provides code execution and file operations in a sandbox environment.
"""
import os
from typing import List, Optional
from langchain.tools import tool
from pydantic import BaseModel, Field
from typing_extensions import Annotated

from agents.components.datagen.tools.persistent_daytona import PersistentDaytonaManager


def get_swe_daytona_tools(daytona_manager: PersistentDaytonaManager) -> List:
    """
    Get Daytona tools configured for SWE agents.
    
    Args:
        daytona_manager: The PersistentDaytonaManager instance for this session
    
    Returns:
        List of Daytona tools for SWE operations
    """
    
    @tool
    async def swe_execute_code(
        code: Annotated[str, "Python code to execute for testing or validation"],
    ) -> str:
        """
        Execute Python code in the Daytona sandbox for testing, validation, or exploration.
        This is useful for running tests, validating implementations, or exploring codebase behavior.
        """
        result, success = await daytona_manager.execute_code(code)
        return f"Execution {'successful' if success else 'failed'}:\n{result}"
    
    @tool
    async def swe_run_command(
        command: Annotated[str, "Shell command to execute in the sandbox"],
        timeout: Annotated[int, "Timeout in seconds (default: 60)"] = 60,
    ) -> str:
        """
        Execute a shell command in the Daytona sandbox.
        Useful for running build commands, tests, git operations, or other development tasks.
        """
        result = await daytona_manager.execute(command, timeout)
        return f"Command result:\n{result}"
    
    @tool
    async def swe_write_file(
        filename: Annotated[str, "Path to the file to write"],
        content: Annotated[str, "Content to write to the file"],
    ) -> str:
        """
        Write content to a file in the Daytona sandbox.
        This creates or overwrites the specified file with the given content.
        """
        result = await daytona_manager.write_file(filename, content)
        return result
    
    @tool
    async def swe_read_file(
        filename: Annotated[str, "Path to the file to read"],
        start: Annotated[Optional[int], "Starting line number (0-based)"] = None,
        end: Annotated[Optional[int], "Ending line number (exclusive)"] = None,
    ) -> str:
        """
        Read content from a file in the Daytona sandbox.
        Optionally specify line ranges to read specific sections.
        """
        success, content = await daytona_manager.read_file(filename)
        if not success:
            return content  # This is an error message
        
        if start is not None or end is not None:
            lines = content.splitlines()
            if start is None:
                start = 0
            selected_lines = lines[start:end]
            content = "\n".join(selected_lines)
        
        return content
    
    @tool
    async def swe_list_files(
        directory: Annotated[str, "Directory path to list files from"] = ".",
    ) -> str:
        """
        List files and directories in the specified path within the Daytona sandbox.
        """
        try:
            command = f"find {directory} -type f | head -50"  # Limit output
            result = await daytona_manager.execute(command, timeout=30)
            return f"Files in {directory}:\n{result}"
        except Exception as e:
            return f"Error listing files: {str(e)}"
    
    @tool
    async def swe_install_package(
        packages: Annotated[str, "Package names to install (space-separated)"],
    ) -> str:
        """
        Install Python packages using pip in the Daytona sandbox.
        """
        command = f"pip install {packages}"
        result = await daytona_manager.execute(command, timeout=300)
        return f"Package installation result:\n{result}"
    
    return [
        swe_execute_code,
        swe_run_command,
        swe_write_file,
        swe_read_file,
        swe_list_files,
        swe_install_package,
    ]


# Tool names for easy reference
SWE_DAYTONA_TOOL_NAMES = [
    "swe_execute_code",
    "swe_run_command", 
    "swe_write_file",
    "swe_read_file",
    "swe_list_files",
    "swe_install_package",
] 