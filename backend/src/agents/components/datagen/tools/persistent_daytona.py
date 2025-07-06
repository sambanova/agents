import mimetypes
import os
import time
import uuid
from ast import Tuple
from typing import Any, Dict, List, Optional

import structlog
from agents.storage.redis_storage import RedisStorage
from agents.utils.code_validator import patch_plot_code_str, strip_markdown_code_blocks

# Import Daytona SDK components - using sync versions
from daytona_sdk import AsyncDaytona as DaytonaClient
from daytona_sdk import CreateSandboxFromSnapshotParams
from daytona_sdk import DaytonaConfig as DaytonaSDKConfig
from langchain.tools import tool
from pydantic import BaseModel, Field
from typing_extensions import Annotated

logger = structlog.get_logger(__name__)


class PersistentDaytonaManager:
    """
    Manages a persistent Daytona client and sandbox throughout the workflow lifecycle.
    Fully synchronous implementation.
    """

    def __init__(
        self,
        user_id: str,
        redis_storage: RedisStorage,
        snapshot: str = "data-analysis:0.0.10",
        file_ids: Optional[List[str]] = None,
    ):
        """
        Initialize the persistent Daytona client. The sandbox will be created on first use.

        Args:
            user_id: User identifier for the session
            redis_storage: Redis storage instance for file management
            snapshot: Daytona snapshot to use for the sandbox
            file_ids: List of file IDs stored in Redis to upload to sandbox root folder
        """
        self._sandbox: Optional[Any] = None
        self._user_id = user_id
        self._redis_storage = redis_storage
        self._snapshot = snapshot
        self._file_ids = file_ids

        api_key = os.getenv("DAYTONA_API_KEY")
        if not api_key:
            raise ValueError("DAYTONA_API_KEY environment variable not set")

        logger.info("Initializing persistent Daytona client", user_id=self._user_id)

        config = DaytonaSDKConfig(api_key=api_key)
        self._client: DaytonaClient = DaytonaClient(config)

    async def _get_sandbox(self):
        """Get the sandbox instance, creating it if it doesn't exist."""
        if self._sandbox is None:
            if not self._client:
                logger.error("Daytona client not initialized.")
                raise RuntimeError("Daytona client not initialized.")

            logger.info(
                "Creating persistent Daytona sandbox on first use",
                user_id=self._user_id,
            )

            params = CreateSandboxFromSnapshotParams(
                snapshot=self._snapshot,
            )
            self._sandbox = await self._client.create(params=params)

            logger.info(
                "Persistent Daytona sandbox created",
                sandbox_id=self._sandbox,
                user_id=self._user_id,
            )

            # Upload files to sandbox root folder if provided
            if self._file_ids:
                await self._upload_files(self._file_ids)

        return self._sandbox

    async def _upload_files(self, file_ids: List[str]) -> None:
        """Upload files to the sandbox root folder."""
        logger.info(
            "Uploading files to sandbox",
            file_count=len(file_ids),
        )

        try:
            for file_id in file_ids:
                await self._upload_file_to_sandbox(file_id)

            logger.info("Files uploaded successfully")

        except Exception as e:
            logger.error("Error uploading files", error=str(e), exc_info=True)
            raise

    async def _upload_file_to_sandbox(self, file_id: str) -> None:
        """Upload a single file to the sandbox root folder."""
        try:
            # Get file data and metadata from Redis
            file_data, file_metadata = await self._redis_storage.get_file(
                self._user_id, file_id
            )

            if not file_data or not file_metadata:
                logger.warning("File not found in Redis, skipping", file_id=file_id)
                return

            # Extract the original filename from metadata
            filename = file_metadata.get("filename", file_id)

            await self._sandbox.fs.upload_file(file_data, filename)
            logger.info("Uploaded file", filename=filename, file_id=file_id)

        except Exception as e:
            logger.error("Error uploading file", file_id=file_id, error=str(e))
            raise

    async def execute_code(self, code: str) -> str:
        """Execute code in the persistent sandbox."""
        sandbox = await self._get_sandbox()
        if not sandbox:
            logger.error("Daytona sandbox not initialized. Call initialize() first.")
            raise RuntimeError(
                "Daytona sandbox not initialized. Call initialize() first."
            )

        try:
            logger.info("Executing code in persistent sandbox", code_preview=code[:100])

            # Strip markdown formatting before processing
            clean_code = strip_markdown_code_blocks(code)

            # Validate the cleaned code
            if not clean_code or len(clean_code.strip()) < 3:
                return "Error: No valid code found after processing input. Please provide valid Python code."

            # Enhanced logging for debugging
            logger.info(
                "Processing code for execution",
                original_length=len(code),
                cleaned_length=len(clean_code),
                first_100_chars=clean_code[:100],
            )

            patched_code, expected_filenames = patch_plot_code_str(clean_code)

            # Execute the code with timeout and error handling
            try:
                response = await sandbox.process.code_run(patched_code)
            except Exception as exec_error:
                logger.error(
                    "Code execution failed in sandbox",
                    error=str(exec_error),
                    exc_info=True,
                )
                return f"Error during code execution: {str(exec_error)}"

            # Ensure result is a string, even if None or other types
            result_str = str(response.result) if response.result is not None else ""

            if response.exit_code != 0:
                error_detail = result_str
                logger.info(
                    "Daytona code execution failed",
                    exit_code=response.exit_code,
                    error_detail=error_detail,
                    original_code_preview=code[:200],
                )
                return f"Error (Exit Code {response.exit_code}): {error_detail}"
            logger.info("Code executed successfully")
            return result_str

        except Exception as e:
            logger.error(
                "Error executing code in persistent sandbox",
                error=str(e),
                exc_info=True,
            )
            return f"Error during code execution: {str(e)}"

    async def execute(self, command: str, timeout: int = 60) -> str:
        """Execute a shell command in the persistent sandbox."""
        sandbox = await self._get_sandbox()
        if not sandbox:
            raise RuntimeError(
                "Daytona sandbox not initialized. Call initialize() first."
            )

        try:
            logger.info("Executing command in persistent sandbox", command=command)

            response = await sandbox.process.exec(command, timeout=timeout)

            # Ensure result is a string, even if None or other types
            result_str = str(response.result) if response.result is not None else ""

            if response.exit_code != 0:
                error_detail = result_str
                logger.error(
                    "Daytona command execution failed",
                    exit_code=response.exit_code,
                    error_detail=error_detail,
                    command=command,
                )
                return f"Error (Exit Code {response.exit_code}): {error_detail}"

            logger.info("Command executed successfully")
            return result_str

        except Exception as e:
            logger.error(
                "Error executing command in persistent sandbox",
                error=str(e),
                exc_info=True,
            )
            return f"Error during command execution: {str(e)}"

    async def list_files(self, directory: str = ".") -> List[str]:
        """List files in the sandbox directory."""
        sandbox = await self._get_sandbox()
        if not sandbox:
            raise RuntimeError("Daytona sandbox not initialized.")

        try:
            # Use actual Daytona SDK call to list files
            files = await sandbox.fs.list_files(directory)
            file_names = [f.name for f in files]

            if not file_names:
                return f"No files found in directory '{directory}'"

            return file_names
        except Exception as e:
            logger.error("Error listing files", directory=directory, error=str(e))
            return f"Error listing files in '{directory}': {str(e)}"

    async def read_file(self, filename: str) -> tuple[bool, str]:
        """Read a file from the sandbox."""
        sandbox = await self._get_sandbox()
        if not sandbox:
            raise RuntimeError("Daytona sandbox not initialized.")

        try:
            content = await sandbox.fs.download_file(filename)
            mime_type = mimetypes.guess_type(filename)[0]
            if mime_type == "text/html" or filename.endswith(".md"):
                try:
                    content_str = (
                        content.decode("utf-8")
                        if isinstance(content, bytes)
                        else str(content)
                    )
                    return True, content_str
                except Exception as e:
                    logger.error("Error decoding file", filename=filename, error=str(e))
                    return False, f"Error decoding file '{filename}': {str(e)}"
            else:
                return True, content
        except Exception as e:
            logger.error("Error reading file", filename=filename, error=str(e))
            return f"Error reading file '{filename}': {str(e)}"

    async def write_file(self, filename: str, content: str) -> str:
        """Write content to a file in the sandbox."""
        sandbox = await self._get_sandbox()
        if not sandbox:
            raise RuntimeError("Daytona sandbox not initialized.")

        try:
            # Convert string content to bytes for upload
            content_bytes = content.encode("utf-8")

            # Use actual Daytona SDK call to upload/write file
            await sandbox.fs.upload_file(content_bytes, filename)

            logger.info("File written successfully", filename=filename)
            return f"File '{filename}' written successfully to sandbox"
        except Exception as e:
            logger.error("Error writing file", filename=filename, error=str(e))
            return f"Error writing file '{filename}': {str(e)}"

    def _clean_code(self, code: str) -> str:
        """Clean up code by removing markdown formatting."""
        # Remove markdown code blocks
        if code.strip().startswith("```"):
            lines = code.split("\n")
            # Remove first line if it's ```python or similar
            if lines[0].strip().startswith("```"):
                lines = lines[1:]
            # Remove last line if it's ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            code = "\n".join(lines)

        return code.strip()

    async def cleanup(self):
        """Clean up the persistent Daytona client and sandbox."""
        try:
            if self._sandbox:
                logger.info(
                    "Deleting persistent Daytona sandbox", sandbox_id=self._sandbox
                )
                await self._sandbox.delete()
                logger.info("Persistent Daytona sandbox deleted successfully")

            # Close the client to properly close HTTP sessions
            if self._client:
                logger.info("Closing persistent Daytona client")
                await self._client.close()
                logger.info("Persistent Daytona client closed successfully")

            # Reset the instance variables
            self._client = None
            self._sandbox = None
            logger.info("Persistent Daytona manager cleaned up successfully")
        except Exception as e:
            logger.error("Error during cleanup", error=str(e), exc_info=True)
            # Still reset variables even if cleanup failed
            self._client = None
            self._sandbox = None


def get_daytona_execute_code(manager: PersistentDaytonaManager):
    """Returns a user-specific version of the daytona_execute_code tool"""

    @tool
    async def user_daytona_execute_code(
        code: Annotated[
            str, "Python code to execute in the persistent Daytona sandbox"
        ],
    ) -> str:
        """
        Execute Python code in a persistent Daytona sandbox.
        The sandbox stays alive between calls, preserving variables and files.
        """
        return await manager.execute_code(code)

    return user_daytona_execute_code


def get_daytona_list_files(manager: PersistentDaytonaManager):
    """Returns a user-specific version of the daytona_list_files tool"""

    @tool
    async def user_daytona_list_files(
        directory: Annotated[str, "Directory to list files from"] = ".",
    ) -> str:
        """List files in the persistent Daytona sandbox directory."""
        return "Files in the sandbox:\n" + "\n".join(
            await manager.list_files(directory)
        )

    return user_daytona_list_files


def get_daytona_read_file(manager: PersistentDaytonaManager):
    """Returns a user-specific version of the daytona_read_file tool"""

    @tool
    async def user_daytona_read_file(
        filename: Annotated[str, "Name of the file to read from the sandbox"],
    ) -> str:
        """Read a file from the persistent Daytona sandbox."""
        _, content = await manager.read_file(filename)
        return content

    return user_daytona_read_file


def get_daytona_write_file(manager: PersistentDaytonaManager):
    """Returns a user-specific version of the daytona_write_file tool"""

    @tool
    async def user_daytona_write_file(
        filename: Annotated[str, "Name of the file to write"],
        content: Annotated[str, "Content to write to the file"],
    ) -> str:
        """Write content to a file in the persistent Daytona sandbox."""
        return await manager.write_file(filename, content)

    return user_daytona_write_file


def get_daytona_create_document(manager: PersistentDaytonaManager):
    """Returns a user-specific version of the daytona_create_document tool"""

    @tool
    async def user_daytona_create_document(
        points: Annotated[List[str], "List of points to be included in the document"],
        filename: Annotated[str, "Name of the file to save the document"],
    ) -> str:
        """
        Create and save a text document in Markdown format in the persistent Daytona sandbox.

        This function takes a list of points and writes them as numbered items in a Markdown file.
        """
        try:
            # Create the markdown content with numbered points
            content = ""
            for i, point in enumerate(points, 1):
                content += f"{i}. {point}\n"

            # Write the document to the sandbox
            result = await manager.write_file(filename, content)
            logger.info(
                "Document created successfully in sandbox",
                filename=filename,
                points_count=len(points),
            )
            return f"Document '{filename}' created successfully in sandbox with {len(points)} points"

        except Exception as e:
            logger.error(
                "Error creating document in sandbox", filename=filename, error=str(e)
            )
            return f"Error creating document '{filename}': {str(e)}"

    return user_daytona_create_document


# User-specific version of the tool
def get_daytona_read_document(manager: PersistentDaytonaManager):
    """Returns a user-specific version of the daytona_read_document tool"""

    @tool
    async def user_daytona_read_document(
        filename: Annotated[str, "Name of the file to read"],
        start: Annotated[Optional[int], "Starting line number to read from"] = None,
        end: Annotated[Optional[int], "Ending line number to read to"] = None,
    ) -> str:
        """
        Read the document from the persistent Daytona sandbox.

        This function reads the specified file from the sandbox and returns its content.
        Optionally, it can return a specific range of lines.

        Args:
            filename: Name of the file to read
            start: Starting line number to read from (0-based indexing)
            end: Ending line number to read to (exclusive)

        Returns:
            str: The content of the document or an error message.
        """
        try:
            # Read the file content from sandbox
            success, content = await manager.read_file(filename)

            # Check if file read was successful (not an error message)
            if not success:
                return content

            # Split content into lines for range reading
            lines = content.splitlines()

            # Handle line range selection
            if start is None:
                start = 0

            # Get the specified range of lines
            selected_lines = lines[start:end]
            result_content = "\n".join(selected_lines)

            logger.info(
                "Document read successfully from sandbox",
                filename=filename,
                total_lines=len(lines),
                lines_returned=len(selected_lines),
                start=start,
                end=end,
            )

            return result_content

        except Exception as e:
            logger.error(
                "Error reading document from sandbox", filename=filename, error=str(e)
            )
            return f"Error reading document '{filename}': {str(e)}"

    return user_daytona_read_document


# User-specific version of the tool
def get_daytona_edit_document(manager: PersistentDaytonaManager):
    """Returns a user-specific version of the daytona_edit_document tool"""

    @tool
    async def user_daytona_edit_document(
        filename: Annotated[str, "Name of the file to edit"],
        inserts: Annotated[
            Dict[int, str], "Dictionary of line numbers and text to insert"
        ],
    ) -> str:
        """
        Edit the document in the persistent Daytona sandbox by inserting text at specific line numbers.

        This function reads the existing file, inserts new text at specified line numbers,
        and saves the modified document back to the sandbox.

        Args:
            filename (str): Name of the file to edit.
            inserts (Dict[int, str]): Dictionary where keys are line numbers (1-based) and values are text to insert.

        Returns:
            str: A message indicating the result of the operation.

        Example:
            inserts = dict([(1, "This is the first line to insert."), (3, "This is the third line to insert.")])
            result = await daytona_edit_document(filename="document.md", inserts=inserts)
        """
        try:
            # Read the existing file content from sandbox
            success, content = await manager.read_file(filename)

            # Check if file read was successful (not an error message)
            if not success:
                return content

            # Split content into lines (preserve line endings)
            lines = content.splitlines(keepends=True)

            # Convert to list without line endings for easier processing
            lines_no_endings = [line.rstrip("\n\r") for line in lines]

            # Sort inserts by line number to process from top to bottom
            sorted_inserts = sorted(inserts.items())

            # Process inserts in reverse order to maintain line numbering
            for line_number, text in reversed(sorted_inserts):
                if 1 <= line_number <= len(lines_no_endings) + 1:
                    # Insert at the specified line (convert from 1-based to 0-based indexing)
                    lines_no_endings.insert(line_number - 1, text)
                else:
                    logger.error(f"Line number out of range: {line_number}")
                    return f"Error: Line number {line_number} is out of range. Document has {len(lines_no_endings)} lines."

            # Reconstruct the content with newlines
            modified_content = "\n".join(lines_no_endings)

            # Write the modified content back to the sandbox
            result = await manager.write_file(filename, modified_content)

            logger.info(
                "Document edited successfully in sandbox",
                filename=filename,
                original_lines=len(lines),
                final_lines=len(lines_no_endings),
                inserts_count=len(inserts),
            )

            return f"Document '{filename}' edited successfully in sandbox. Added {len(inserts)} insertions."

        except Exception as e:
            logger.error(
                "Error editing document in sandbox", filename=filename, error=str(e)
            )
            return f"Error editing document '{filename}': {str(e)}"

    return user_daytona_edit_document


# User-specific version of the tool
def get_daytona_describe_data(manager: PersistentDaytonaManager):
    """Returns a user-specific version of the daytona_describe_data tool"""

    @tool
    async def user_daytona_describe_data(
        filename: Annotated[str, "Name of the file to describe"],
    ) -> str:
        """
        Describe the data in a CSV file in the persistent Daytona sandbox.

        This function attempts to read a CSV file using different encodings and
        returns information about the data structure and first few rows.
        """
        # First check if file exists
        try:

            # Generate pandas analysis code to run in sandbox
            analysis_code = f'''
import pandas as pd
import io

def analyze_csv_data(file_path: str) -> str:
    """Analyze CSV data with multiple encoding attempts"""
    encodings = ["utf-8", "latin1", "iso-8859-1", "cp1252"]
    
    for encoding in encodings:
        try:
            # Read the CSV file
            data = pd.read_csv(file_path, encoding=encoding)
            
            # Get basic information
            info = {{
                "encoding_used": encoding,
                "shape": data.shape,
                "columns": list(data.columns),
                "dtypes": dict(data.dtypes.astype(str)),
                "null_counts": dict(data.isnull().sum()),
                "memory_usage": data.memory_usage(deep=True).sum()
            }}
            
            # Get sample data (first 5 rows) as string table
            sample_data_str = data.head().to_string(max_cols=10, max_colwidth=50)
            
            # Generate summary
            summary = f"""
CSV Data Analysis for: {{file_path}}
=====================================
Encoding: {{encoding}}
Shape: {{data.shape[0]}} rows, {{data.shape[1]}} columns
Memory Usage: {{info["memory_usage"] / 1024 / 1024:.2f}} MB

Columns and Data Types:
{{chr(10).join([f"  - {{col}}: {{dtype}}" for col, dtype in info["dtypes"].items()])}}

Missing Values:
{{chr(10).join([f"  - {{col}}: {{count}} missing" for col, count in info["null_counts"].items() if count > 0])}}

Sample Data (first 5 rows):
{{sample_data_str}}
"""
            return summary
            
        except Exception as e:
            continue
    
    return f"Error: Unable to read CSV file '{{file_path}}' with any supported encoding (utf-8, latin1, iso-8859-1, cp1252)"

# Analyze the data
result = analyze_csv_data("{filename}")
print(result)
'''

            # Execute the analysis code in the sandbox
            result = await manager.execute_code(analysis_code)
            return result

        except Exception as e:
            logger.error(
                "Error analyzing CSV data",
                filename=filename,
                error=str(e),
                exc_info=True,
            )
            return f"Error analyzing CSV data: {str(e)}"

    return user_daytona_describe_data


# User-specific version of the tool
def get_daytona_pip_install(manager: PersistentDaytonaManager):
    """Returns a user-specific version of the daytona_pip_install tool"""

    @tool
    async def user_daytona_pip_install(
        packages: Annotated[
            str,
            "Package name(s) to install. Can be a single package or multiple packages separated by spaces",
        ],
    ) -> str:
        """
        Install Python packages using pip in the persistent Daytona sandbox. Only install packages after you have run some code and observed that some packages are missing.

        This function executes pip install commands in the sandbox to install the specified packages.
        You can install single or multiple packages at once.

        Args:
            packages: Package name(s) to install. Examples: "pandas", "numpy matplotlib", "requests==2.28.0"

        Returns:
            str: Success message or error details from the installation process.

        Examples:
            - Install single package: packages="pandas"
            - Install multiple packages: packages="numpy matplotlib seaborn"
            - Install with version: packages="requests==2.28.0"
        """
        try:
            # Split packages by space and clean them
            package_list = [pkg.strip() for pkg in packages.split() if pkg.strip()]

            if not package_list:
                return "Error: No packages specified for installation"

            # Create pip install command
            pip_command = f"pip install {' '.join(package_list)}"

            logger.info(
                "Installing packages in sandbox",
                packages=package_list,
                command=pip_command,
            )

            # Execute pip install using the manager's execute method
            result = await manager.execute(pip_command, timeout=300)

            # Add success prefix if command succeeded
            if not result.startswith("Error"):
                result = f"Successfully installed: {' '.join(package_list)}\n{result}"

            logger.info(
                "Package installation completed",
                packages=package_list,
                success="Successfully installed" in result,
            )

            return result

        except Exception as e:
            logger.error(
                "Error installing packages in sandbox",
                packages=packages,
                error=str(e),
                exc_info=True,
            )
            return f"Error installing packages '{packages}': {str(e)}"

    return user_daytona_pip_install
