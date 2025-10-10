"""
MCP Tool Wrappers for LangChain

Provides LangChain-compatible tools that execute via MCP protocol.
"""

import asyncio
from typing import Any, Dict, List, Optional, Type

import structlog
from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain.tools import BaseTool
from pydantic import BaseModel, Field, create_model

logger = structlog.get_logger(__name__)


class MCPToolWrapper(BaseTool):
    """
    Base wrapper for MCP tools.
    
    This creates a LangChain tool that executes via MCP protocol.
    """
    
    mcp_connector: Any  # MCPConnector instance
    user_id: str
    mcp_tool_name: str
    
    def _run(
        self,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs
    ) -> str:
        """Synchronous execution (delegates to async)"""
        return asyncio.run(self._arun(run_manager=run_manager, **kwargs))
    
    async def _arun(
        self,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
        **kwargs
    ) -> str:
        """Execute tool via MCP protocol"""
        try:
            logger.debug(
                "Executing MCP tool",
                tool_name=self.mcp_tool_name,
                user_id=self.user_id,
                arguments=kwargs
            )
            
            result = await self.mcp_connector.execute_mcp_tool(
                user_id=self.user_id,
                tool_name=self.mcp_tool_name,
                arguments=kwargs
            )
            
            if not result.get("success"):
                error_msg = result.get("error", "Unknown MCP error")
                logger.error(
                    "MCP tool execution failed",
                    tool_name=self.mcp_tool_name,
                    error=error_msg
                )
                return f"Error: {error_msg}"
            
            # Format the result for LangChain
            tool_result = result.get("result", {})
            
            # If result is a dict, format it nicely
            if isinstance(tool_result, dict):
                if "content" in tool_result:
                    return str(tool_result["content"])
                elif "text" in tool_result:
                    return str(tool_result["text"])
                elif "message" in tool_result:
                    return str(tool_result["message"])
                else:
                    # Format dict as readable text
                    lines = []
                    for key, value in tool_result.items():
                        lines.append(f"{key}: {value}")
                    return "\n".join(lines)
            else:
                return str(tool_result)
                
        except Exception as e:
            error_msg = f"MCP tool execution error: {str(e)}"
            logger.error(
                error_msg,
                tool_name=self.mcp_tool_name,
                user_id=self.user_id,
                exc_info=True
            )
            return error_msg


def create_dynamic_mcp_tool(
    tool_definition: Dict[str, Any],
    mcp_connector: Any,
    user_id: str
) -> Type[MCPToolWrapper]:
    """
    Dynamically create an MCP tool class from a tool definition.
    
    This allows us to create tools based on what the MCP server provides.
    """
    # Extract tool metadata
    tool_name = tool_definition.get("name", "unknown_tool")
    tool_description = tool_definition.get("description", "MCP tool")
    
    # Create Pydantic model for arguments
    input_schema = tool_definition.get("inputSchema", {})
    properties = input_schema.get("properties", {})
    required = input_schema.get("required", [])
    
    # Build field definitions for Pydantic model
    field_definitions = {}
    for prop_name, prop_schema in properties.items():
        prop_type = prop_schema.get("type", "string")
        prop_description = prop_schema.get("description", "")
        prop_default = ... if prop_name in required else None
        
        # Map JSON schema types to Python types
        type_mapping = {
            "string": str,
            "number": float,
            "integer": int,
            "boolean": bool,
            "array": List[Any],
            "object": Dict[str, Any]
        }
        
        python_type = type_mapping.get(prop_type, str)
        
        # Handle optional fields
        if prop_name not in required:
            python_type = Optional[python_type]
        
        field_definitions[prop_name] = (
            python_type,
            Field(default=prop_default, description=prop_description)
        )
    
    # Create dynamic Pydantic model
    DynamicArgsModel = create_model(
        f"{tool_name}_Args",
        **field_definitions
    ) if field_definitions else None
    
    # Create dynamic tool class
    class DynamicMCPTool(MCPToolWrapper):
        name: str = tool_name
        description: str = tool_description
        args_schema: Optional[Type[BaseModel]] = DynamicArgsModel
        mcp_tool_name: str = tool_name
    
    # Set the class name for debugging
    DynamicMCPTool.__name__ = f"MCP_{tool_name}"
    
    return DynamicMCPTool


def create_mcp_langchain_tools(
    mcp_connector: Any,
    user_id: str,
    tool_ids: List[str]
) -> List[BaseTool]:
    """
    Create LangChain tools from MCP tool definitions.
    
    This queries the MCP server for available tools and creates
    LangChain wrappers for the requested ones.
    """
    tools = []
    
    try:
        # Get tool definitions from MCP server
        # Note: This is synchronous for now, should be made async
        import asyncio
        mcp_tools = asyncio.run(mcp_connector.get_mcp_tools())
        
        # Create mapping of tool names to definitions
        tool_map = {tool["name"]: tool for tool in mcp_tools}
        
        # Create LangChain tools for requested IDs
        for tool_id in tool_ids:
            if tool_id in tool_map:
                tool_def = tool_map[tool_id]
                
                # Create dynamic tool class
                tool_class = create_dynamic_mcp_tool(
                    tool_def,
                    mcp_connector,
                    user_id
                )
                
                # Instantiate the tool
                tool_instance = tool_class(
                    mcp_connector=mcp_connector,
                    user_id=user_id
                )
                
                tools.append(tool_instance)
                
                logger.info(
                    "Created MCP tool",
                    tool_name=tool_id,
                    user_id=user_id
                )
            else:
                logger.warning(
                    "MCP tool not found",
                    tool_name=tool_id,
                    available_tools=list(tool_map.keys())
                )
        
    except Exception as e:
        logger.error(
            "Failed to create MCP tools",
            user_id=user_id,
            error=str(e),
            exc_info=True
        )
    
    return tools


# Pre-defined tool wrappers for common MCP tools
# These provide better type hints and documentation

class JiraCreateIssueInput(BaseModel):
    """Input for creating a Jira issue"""
    project: str = Field(description="Project key (e.g., 'PROJ')")
    summary: str = Field(description="Issue summary/title")
    description: str = Field(default="", description="Issue description")
    issue_type: str = Field(default="Task", description="Issue type (Bug, Task, Story)")
    priority: str = Field(default="Medium", description="Priority (Highest, High, Medium, Low, Lowest)")
    assignee: Optional[str] = Field(None, description="Assignee username")
    labels: Optional[List[str]] = Field(None, description="Issue labels")


class JiraSearchIssuesInput(BaseModel):
    """Input for searching Jira issues"""
    jql: str = Field(description="JQL query string")
    max_results: int = Field(default=10, description="Maximum number of results")
    fields: Optional[List[str]] = Field(default=None, description="Fields to include in response")


class ConfluenceCreatePageInput(BaseModel):
    """Input for creating a Confluence page"""
    space: str = Field(description="Space key")
    title: str = Field(description="Page title")
    content: str = Field(description="Page content (HTML or Markdown)")
    parent_id: Optional[str] = Field(None, description="Parent page ID")


class ConfluenceSearchInput(BaseModel):
    """Input for searching Confluence"""
    query: str = Field(description="Search query")
    space: Optional[str] = Field(None, description="Limit to specific space")
    max_results: int = Field(default=10, description="Maximum results")


# Tool class definitions
class JiraCreateIssueTool(MCPToolWrapper):
    """Create a new Jira issue"""
    name: str = "jira_create_issue"
    description: str = "Create a new issue in Jira"
    args_schema: Type[BaseModel] = JiraCreateIssueInput
    mcp_tool_name: str = "jira_create_issue"


class JiraSearchIssuesTool(MCPToolWrapper):
    """Search for Jira issues"""
    name: str = "jira_search_issues"
    description: str = "Search for Jira issues using JQL"
    args_schema: Type[BaseModel] = JiraSearchIssuesInput
    mcp_tool_name: str = "jira_search"


class ConfluenceCreatePageTool(MCPToolWrapper):
    """Create a Confluence page"""
    name: str = "confluence_create_page"
    description: str = "Create a new page in Confluence"
    args_schema: Type[BaseModel] = ConfluenceCreatePageInput
    mcp_tool_name: str = "confluence_create_page"


class ConfluenceSearchTool(MCPToolWrapper):
    """Search Confluence"""
    name: str = "confluence_search"
    description: str = "Search for content in Confluence"
    args_schema: Type[BaseModel] = ConfluenceSearchInput
    mcp_tool_name: str = "confluence_search"


# Mapping of common tool IDs to classes
PREDEFINED_TOOLS = {
    "jira_create_issue": JiraCreateIssueTool,
    "jira_search_issues": JiraSearchIssuesTool,
    "confluence_create_page": ConfluenceCreatePageTool,
    "confluence_search": ConfluenceSearchTool,
}


def create_predefined_mcp_tools(
    mcp_connector: Any,
    user_id: str,
    tool_ids: List[str]
) -> List[BaseTool]:
    """
    Create MCP tools using predefined wrappers.
    
    This provides better type safety than dynamic tools.
    """
    tools = []
    
    for tool_id in tool_ids:
        if tool_id in PREDEFINED_TOOLS:
            tool_class = PREDEFINED_TOOLS[tool_id]
            tool_instance = tool_class(
                mcp_connector=mcp_connector,
                user_id=user_id
            )
            tools.append(tool_instance)
            logger.info(
                "Created predefined MCP tool",
                tool_name=tool_id,
                user_id=user_id
            )
        else:
            logger.debug(
                "No predefined tool for ID",
                tool_id=tool_id
            )
    
    return tools