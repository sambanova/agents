import asyncio
import mimetypes
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import structlog

# Import Daytona SDK components
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
        data_sources: Optional[Dict[str, Any]] = None,
    ) -> "PersistentDaytonaManager":
        """
        Initialize the persistent Daytona client and sandbox.

        Args:
            user_id: User identifier for the session
            redis_storage: Redis storage instance for file management
            snapshot: Daytona snapshot to use for the sandbox
            data_sources: Dictionary containing data to upload to sandbox root folder.
                         Can contain:
                         - 'files': List of file paths to upload
                         - 'directories': List of directory paths to upload
                         - 'content': Dict of filename -> content strings to create
        """
        instance = cls()

        if instance._client is None:
            api_key = os.getenv("DAYTONA_API_KEY")
            if not api_key:
                raise ValueError("DAYTONA_API_KEY environment variable not set")

            logger.info("Initializing persistent Daytona client", user_id=user_id)

            # Create persistent client
            config = DaytonaSDKConfig(api_key=api_key)
            instance._client = DaytonaClient(config)
            instance._user_id = user_id
            instance._redis_storage = redis_storage

            # Create persistent sandbox
            params = CreateSandboxFromSnapshotParams(snapshot=snapshot)
            instance._sandbox = await instance._client.create(params=params)

            logger.info(
                "Persistent Daytona sandbox created",
                sandbox_id=getattr(instance._sandbox, "id", "unknown"),
                user_id=user_id,
            )

            # Upload data to sandbox root folder if provided
            if data_sources:
                await instance._upload_data_sources(data_sources)

        return instance

    async def _upload_data_sources(self, data_sources: Dict[str, Any]) -> None:
        """Upload data sources to the sandbox root folder."""
        logger.info(
            "Uploading data sources to sandbox",
            data_sources_keys=list(data_sources.keys()),
        )

        try:
            # Upload individual files
            if "files" in data_sources:
                for file_path in data_sources["files"]:
                    await self._upload_file_to_sandbox(file_path)

            # Upload directories
            if "directories" in data_sources:
                for dir_path in data_sources["directories"]:
                    await self._upload_directory_to_sandbox(dir_path)

            # Create files from content
            if "content" in data_sources:
                for filename, content in data_sources["content"].items():
                    await self.write_file(filename, content)
                    logger.info("Created file from content", filename=filename)

            logger.info("Data sources uploaded successfully")

        except Exception as e:
            logger.error("Error uploading data sources", error=str(e), exc_info=True)
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

            # Try to decode as text, fallback to binary upload
            try:
                text_content = content.decode("utf-8")
                await self.write_file(filename, text_content)
                logger.info(
                    "Uploaded text file", filename=filename, source_path=file_path
                )
            except UnicodeDecodeError:
                # For binary files, upload directly
                await self._sandbox.fs.upload_file(filename, content)
                logger.info(
                    "Uploaded binary file", filename=filename, source_path=file_path
                )

        except Exception as e:
            logger.error("Error uploading file", file_path=file_path, error=str(e))
            raise

    async def _upload_directory_to_sandbox(self, dir_path: str) -> None:
        """Upload all files from a directory to the sandbox root folder."""
        if not os.path.exists(dir_path) or not os.path.isdir(dir_path):
            logger.warning("Directory not found, skipping", dir_path=dir_path)
            return

        try:
            for root, dirs, files in os.walk(dir_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    # Create relative path for sandbox
                    rel_path = os.path.relpath(file_path, dir_path)

                    with open(file_path, "rb") as f:
                        content = f.read()

                    # Try to decode as text, fallback to binary upload
                    try:
                        text_content = content.decode("utf-8")
                        await self.write_file(rel_path, text_content)
                        logger.info(
                            "Uploaded text file from directory",
                            filename=rel_path,
                            source_path=file_path,
                        )
                    except UnicodeDecodeError:
                        # For binary files, upload directly
                        await self._sandbox.fs.upload_file(rel_path, content)
                        logger.info(
                            "Uploaded binary file from directory",
                            filename=rel_path,
                            source_path=file_path,
                        )

        except Exception as e:
            logger.error("Error uploading directory", dir_path=dir_path, error=str(e))
            raise

    async def execute_code(self, code: str) -> str:
        """Execute code in the persistent sandbox."""
        if not self._sandbox:
            raise RuntimeError(
                "Daytona sandbox not initialized. Call initialize() first."
            )

        try:
            logger.info("Executing code in persistent sandbox", code_preview=code[:100])

            # Clean up the code (remove markdown formatting, etc.)
            clean_code = self._clean_code(code)

            if not clean_code or len(clean_code.strip()) < 3:
                return "Error: No valid code found after processing input. Please provide valid Python code."

            # Execute the code
            response = await self._sandbox.process.code_run(clean_code)

            # Process the response
            result_str = str(response.result) if response.result is not None else ""

            if response.exit_code != 0:
                error_detail = result_str
                logger.error(
                    "Code execution failed",
                    exit_code=response.exit_code,
                    error_detail=error_detail[:500],
                )
                return f"Error (Exit Code {response.exit_code}): {error_detail}"

            logger.info("Code executed successfully", result_preview=result_str[:500])

            # Process any generated files
            files_info = await self._process_generated_files()
            if files_info:
                result_str += "\n\n" + files_info

            return result_str

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
            files = await self._sandbox.fs.list_files(directory)
            file_list = [f.name for f in files]
            return f"Files in {directory}:\n" + "\n".join(file_list)
        except Exception as e:
            logger.error("Error listing files", error=str(e))
            return f"Error listing files: {str(e)}"

    async def read_file(self, filename: str) -> str:
        """Read a file from the sandbox."""
        if not self._sandbox:
            raise RuntimeError("Daytona sandbox not initialized.")

        try:
            content = await self._sandbox.fs.download_file(filename)
            if isinstance(content, bytes):
                try:
                    return content.decode("utf-8")
                except UnicodeDecodeError:
                    return f"File '{filename}' contains binary data (size: {len(content)} bytes)"
            return str(content)
        except Exception as e:
            logger.error("Error reading file", filename=filename, error=str(e))
            return f"Error reading file '{filename}': {str(e)}"

    async def write_file(self, filename: str, content: str) -> str:
        """Write content to a file in the sandbox."""
        if not self._sandbox:
            raise RuntimeError("Daytona sandbox not initialized.")

        try:
            await self._sandbox.fs.upload_file(filename, content.encode("utf-8"))
            logger.info("File written successfully", filename=filename)
            return f"File '{filename}' written successfully"
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

    async def _process_generated_files(self) -> str:
        """Process any files generated during code execution."""
        if not self._sandbox or not self._redis_storage:
            return ""

        try:
            files = await self._sandbox.fs.list_files(".")
            file_info = []

            supported_extensions = [
                "image/png",
                "image/jpg",
                "image/jpeg",
                "image/gif",
                "image/svg",
                "application/pdf",
                "text/html",
                "text/markdown",
                "text/plain",
                "text/csv",
            ]

            for file in files:
                if file.name.startswith("."):  # Skip hidden files
                    continue

                mime_type, _ = mimetypes.guess_type(file.name)
                if mime_type in supported_extensions:
                    try:
                        content = await self._sandbox.fs.download_file(file.name)
                        file_id = str(uuid.uuid4())

                        # Store in Redis
                        await self._redis_storage.put_file(
                            self._user_id,
                            file_id,
                            data=content,
                            filename=file.name,
                            format=mime_type,
                            upload_timestamp=time.time(),
                            indexed=False,
                            source="persistent_daytona",
                        )

                        if mime_type.startswith("image/"):
                            file_info.append(
                                f"![{file.name}](redis-chart:{file_id}:{self._user_id})"
                            )
                        else:
                            file_info.append(f"![{file.name}](attachment:{file_id})")

                    except Exception as e:
                        logger.error(
                            "Error processing file", filename=file.name, error=str(e)
                        )

            return "\n".join(file_info) if file_info else ""

        except Exception as e:
            logger.error("Error processing generated files", error=str(e))
            return ""

    async def cleanup(self):
        """Clean up the persistent client and sandbox."""
        if self._client:
            try:
                logger.info("Cleaning up persistent Daytona client")
                await self._client.close()
                self._client = None
                self._sandbox = None
                logger.info("Persistent Daytona client cleaned up successfully")
            except Exception as e:
                logger.error("Error during Daytona cleanup", error=str(e))

    @classmethod
    def reset(cls):
        """Reset the singleton instance (useful for testing)."""
        if cls._instance and cls._instance._client:
            # Note: This is sync, so cleanup should be called before reset
            pass
        cls._instance = None


# Global manager instance
_daytona_manager: Optional[PersistentDaytonaManager] = None


async def get_or_create_daytona_manager(
    user_id: str,
    redis_storage: Optional[Any] = None,
    data_sources: Optional[Dict[str, Any]] = None,
) -> PersistentDaytonaManager:
    """Get or create the global Daytona manager."""
    global _daytona_manager
    if _daytona_manager is None:
        _daytona_manager = await PersistentDaytonaManager.initialize(
            user_id, redis_storage, data_sources=data_sources
        )
    return _daytona_manager


# Tool definitions using the persistent manager
@tool
def daytona_execute_code(
    code: Annotated[str, "Python code to execute in the persistent Daytona sandbox"],
) -> str:
    """
    Execute Python code in a persistent Daytona sandbox.
    The sandbox stays alive between calls, preserving variables and files.
    """
    # This is a sync wrapper - the actual execution will be async
    import asyncio

    async def _execute():
        manager = await get_or_create_daytona_manager(
            "default_user"
        )  # You might want to pass user_id
        return await manager.execute_code(code)

    try:
        # Try to get existing event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, we need to create a task
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _execute())
                return future.result()
        else:
            return loop.run_until_complete(_execute())
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(_execute())


@tool
def daytona_list_files(
    directory: Annotated[str, "Directory to list files from"] = ".",
) -> str:
    """List files in the persistent Daytona sandbox directory."""
    import asyncio

    async def _list_files():
        manager = await get_or_create_daytona_manager("default_user")
        return await manager.list_files(directory)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _list_files())
                return future.result()
        else:
            return loop.run_until_complete(_list_files())
    except RuntimeError:
        return asyncio.run(_list_files())


@tool
def daytona_read_file(
    filename: Annotated[str, "Name of the file to read from the sandbox"],
) -> str:
    """Read a file from the persistent Daytona sandbox."""
    import asyncio

    async def _read_file():
        manager = await get_or_create_daytona_manager("default_user")
        return await manager.read_file(filename)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _read_file())
                return future.result()
        else:
            return loop.run_until_complete(_read_file())
    except RuntimeError:
        return asyncio.run(_read_file())


@tool
def daytona_write_file(
    filename: Annotated[str, "Name of the file to write"],
    content: Annotated[str, "Content to write to the file"],
) -> str:
    """Write content to a file in the persistent Daytona sandbox."""
    import asyncio

    async def _write_file():
        manager = await get_or_create_daytona_manager("default_user")
        return await manager.write_file(filename, content)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _write_file())
                return future.result()
        else:
            return loop.run_until_complete(_write_file())
    except RuntimeError:
        return asyncio.run(_write_file())


# Cleanup function to be called at workflow end
async def cleanup_persistent_daytona():
    """Clean up the persistent Daytona manager. Call this at the end of your workflow."""
    global _daytona_manager
    if _daytona_manager:
        await _daytona_manager.cleanup()
        _daytona_manager = None


# Context manager for automatic cleanup
@asynccontextmanager
async def persistent_daytona_context(
    user_id: str,
    redis_storage: Optional[Any] = None,
    data_sources: Optional[Dict[str, Any]] = None,
):
    """Context manager for persistent Daytona lifecycle management."""
    manager = await PersistentDaytonaManager.initialize(
        user_id, redis_storage, data_sources=data_sources
    )
    try:
        yield manager
    finally:
        await manager.cleanup()


# Helper function to create data sources configuration
def create_data_sources_config(
    files: Optional[List[str]] = None,
    directories: Optional[List[str]] = None,
    content: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Helper function to create data_sources configuration for PersistentDaytonaManager.

    Args:
        files: List of file paths to upload to sandbox root
        directories: List of directory paths to upload to sandbox root
        content: Dictionary of filename -> content to create in sandbox

    Returns:
        Dictionary formatted for use with PersistentDaytonaManager.initialize()

    Example:
        # Upload specific files and create a config file
        data_sources = create_data_sources_config(
            files=['/path/to/data.csv', '/path/to/script.py'],
            directories=['/path/to/datasets'],
            content={'config.json': '{"setting": "value"}'}
        )
    """
    config = {}

    if files:
        config["files"] = files

    if directories:
        config["directories"] = directories

    if content:
        config["content"] = content

    return config if config else None
