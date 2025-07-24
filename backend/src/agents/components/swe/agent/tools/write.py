from langchain_core.tools import tool
import os
from gitingest import ingest


@tool(parse_docstring=True)
def create_file(path: str, content: str) -> str:
    """Create a new file at the specified path with the given content. If the file already exists,
    returns an error message instead of overwriting.

    Args:
        path: The path from the root of the folder to the file
        content: The text content to write to the file

    Returns:
        str: A success message with the file path, or an error message if creation failed
    """
    try:
        # Check if file already exists
        # Ensure the directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully created file at {path}"
    except Exception as e:
        return f"Error creating file: {str(e)}"


@tool(parse_docstring=True)
def write_to_file(path: str, content: str) -> str:
    """Override the content of an existing file at the specified path. If the file doesn't exist,
    returns an error message instead of creating it.

    Args:
        path: The path to the file to override
        content: The new text content that will completely replace the current content

    Returns:
        str: A success message with the file path, or an error message if writing failed
    """
    try:
        if not os.path.exists(path):
            return f"Error: File {path} does not exist"

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully overridden file at {path}"
    except Exception as e:
        return f"Error overriding file: {str(e)}"


@tool(parse_docstring=True)
def get_files_structure(directory: str = "./workspace_repo") -> str:
    """Generate a JSON representation of the file and directory structure starting from the specified directory.
    Uses gitingest to analyze the codebase structure.

    Args:
        directory: The root directory to start scanning from (defaults to "./workspace_repo")

    Returns:
        str: A string representing the hierarchical directory structure and file listing
    """
    summary, tree, content = ingest(directory)
    return tree


# List of available tools
write_tools = [create_file, write_to_file, get_files_structure]
write_tools_map = {tool.name: tool for tool in write_tools}
