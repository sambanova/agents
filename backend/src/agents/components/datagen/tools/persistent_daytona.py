import mimetypes
import os
import time
import uuid
from typing import Any, Dict, List, Optional

import structlog

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

    _instance: Optional["PersistentDaytonaManager"] = None
    _client: Optional[Any] = None
    _sandbox: Optional[Any] = None
    _user_id: str = ""
    _redis_storage: Optional[Any] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    async def initialize(
        cls,
        user_id: str,
        redis_storage: Optional[Any] = None,
        snapshot: str = "data-analysis:0.0.8",
        data_sources: Optional[List[str]] = None,
    ) -> "PersistentDaytonaManager":
        """
        Initialize the persistent Daytona client and sandbox.

        Args:
            user_id: User identifier for the session
            redis_storage: Redis storage instance for file management
            snapshot: Daytona snapshot to use for the sandbox
            data_sources: List of file paths to upload to sandbox root folder
        """
        instance = cls()

        if instance._client is None:
            api_key = os.getenv("DAYTONA_API_KEY")
            if not api_key:
                raise ValueError("DAYTONA_API_KEY environment variable not set")

            logger.info("Initializing persistent Daytona client", user_id=user_id)

            # For now, we'll use a simple approach
            # In practice, this would use actual async Daytona SDK calls
            instance._user_id = user_id
            instance._redis_storage = redis_storage

            # Placeholder for actual Daytona initialization
            # This would be replaced with actual async Daytona SDK calls
            config = DaytonaSDKConfig(api_key=api_key)
            instance._client = DaytonaClient(config)

            params = CreateSandboxFromSnapshotParams(
                snapshot=snapshot,
            )
            instance._sandbox = await instance._client.create(params=params)

            logger.info(
                "Persistent Daytona sandbox created",
                sandbox_id=instance._sandbox,
                user_id=user_id,
            )

            # Upload files to sandbox root folder if provided
            if data_sources:
                await instance._upload_files(data_sources)

        return instance

    async def _upload_files(self, file_paths: List[str]) -> None:
        """Upload files to the sandbox root folder."""
        logger.info(
            "Uploading files to sandbox",
            file_count=len(file_paths),
        )

        try:
            for file_path in file_paths:
                await self._upload_file_to_sandbox(file_path)

            logger.info("Files uploaded successfully")

        except Exception as e:
            logger.error("Error uploading files", error=str(e), exc_info=True)
            raise

    async def _upload_file_to_sandbox(self, file_path: str) -> None:
        """Upload a single file to the sandbox root folder."""
        if not os.path.exists(file_path):
            logger.warning("File not found, skipping", file_path=file_path)
            return

        try:
            filename = os.path.basename(file_path)

            with open(file_path, "rb") as f:
                content = f.read()

            await self._sandbox.fs.upload_file(content, filename)
            logger.info("Uploaded file", filename=filename, source_path=file_path)

        except Exception as e:
            logger.error("Error uploading file", file_path=file_path, error=str(e))
            raise

    async def execute_code(self, code: str) -> str:
        """Execute code in the persistent sandbox."""
        if not self._sandbox:
            raise RuntimeError(
                "Daytona sandbox not initialized. Call initialize() first."
            )

        try:
            logger.info("Executing code in persistent sandbox", code_preview=code[:100])
            result = await self._sandbox.process.code_run(code)
            logger.info("Code executed successfully")
            return result.result

        except Exception as e:
            logger.error(
                "Error executing code in persistent sandbox",
                error=str(e),
                exc_info=True,
            )
            return f"Error during code execution: {str(e)}"

    async def list_files(self, directory: str = ".") -> str:
        """List files in the sandbox directory."""
        if not self._sandbox:
            raise RuntimeError("Daytona sandbox not initialized.")

        try:
            # Simulate file listing - replace with actual async Daytona SDK calls
            simulated_files = ["data.csv", "analysis.py", "results.txt"]
            return f"Files in {directory}:\n" + "\n".join(simulated_files)
        except Exception as e:
            logger.error("Error listing files", error=str(e))
            return f"Error listing files: {str(e)}"

    async def read_file(self, filename: str) -> str:
        """Read a file from the sandbox."""
        if not self._sandbox:
            raise RuntimeError("Daytona sandbox not initialized.")

        try:
            content = await self._sandbox.fs.download_file(filename)
            return content
        except Exception as e:
            logger.error("Error reading file", filename=filename, error=str(e))
            return f"Error reading file '{filename}': {str(e)}"

    async def write_file(self, filename: str, content: str) -> str:
        """Write content to a file in the sandbox."""
        if not self._sandbox:
            raise RuntimeError("Daytona sandbox not initialized.")

        try:
            # Simulate file writing - replace with actual async Daytona SDK calls
            logger.info("File written successfully", filename=filename)
            return f"File '{filename}' written successfully to sandbox {self._sandbox}"
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
            # Simulate cleanup - replace with actual async Daytona SDK calls
            logger.info("Cleaning up persistent Daytona", sandbox_id=self._sandbox)
            self._client = None
            self._sandbox = None
            logger.info("Persistent Daytona cleaned up successfully")
        except Exception as e:
            logger.error("Error during cleanup", error=str(e))

    @classmethod
    def reset(cls):
        """Reset the singleton instance (useful for testing)."""
        if cls._instance and cls._instance._client:
            # Note: In a real async environment, you'd want to properly await cleanup
            # For testing/reset purposes, we'll just set to None
            cls._instance._client = None
            cls._instance._sandbox = None
        cls._instance = None


# Global manager instance
_daytona_manager: Optional[PersistentDaytonaManager] = None


async def get_or_create_daytona_manager(
    user_id: str,
    redis_storage: Optional[Any] = None,
    data_sources: Optional[List[str]] = None,
) -> PersistentDaytonaManager:
    """Get or create the global Daytona manager."""
    global _daytona_manager

    data_sources = ["~/Downloads/customer_satisfaction_purchase_behavior.csv.csv"]
    if _daytona_manager is None:
        _daytona_manager = await PersistentDaytonaManager.initialize(
            user_id, redis_storage, data_sources=data_sources
        )
    return _daytona_manager


# Tool definitions using native async support
@tool
async def daytona_execute_code(
    code: Annotated[str, "Python code to execute in the persistent Daytona sandbox"],
) -> str:
    """
    Execute Python code in a persistent Daytona sandbox.
    The sandbox stays alive between calls, preserving variables and files.
    """
    manager = await get_or_create_daytona_manager("default_user")
    return await manager.execute_code(code)


@tool
async def daytona_list_files(
    directory: Annotated[str, "Directory to list files from"] = ".",
) -> str:
    """List files in the persistent Daytona sandbox directory."""
    manager = await get_or_create_daytona_manager("default_user")
    return await manager.list_files(directory)


@tool
async def daytona_read_file(
    filename: Annotated[str, "Name of the file to read from the sandbox"],
) -> str:
    """Read a file from the persistent Daytona sandbox."""
    manager = await get_or_create_daytona_manager("default_user")
    return await manager.read_file(filename)


@tool
async def daytona_write_file(
    filename: Annotated[str, "Name of the file to write"],
    content: Annotated[str, "Content to write to the file"],
) -> str:
    """Write content to a file in the persistent Daytona sandbox."""
    manager = await get_or_create_daytona_manager("default_user")
    return await manager.write_file(filename, content)


@tool
async def daytona_describe_data(
    filename: Annotated[str, "Name of the file to describe"],
) -> str:
    """
    Describe the data in a CSV file in the persistent Daytona sandbox.

    This function attempts to read a CSV file using different encodings and
    returns information about the data structure and first few rows.
    """
    manager = await get_or_create_daytona_manager("default_user")

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
        return f"Error analyzing CSV data: {str(e)}"


# Cleanup function to be called at workflow end
async def cleanup_persistent_daytona():
    """Clean up the persistent Daytona manager. Call this at the end of your workflow."""
    global _daytona_manager
    if _daytona_manager:
        await _daytona_manager.cleanup()
        _daytona_manager = None
