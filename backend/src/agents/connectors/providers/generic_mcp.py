"""
Generic MCP Connector

Allows users to add custom MCP servers dynamically via UI.
This connector can be instantiated with any MCP server URL and OAuth config.
"""

from typing import Any, Dict, List, Optional

import structlog
from agents.connectors.core.base_connector import ConnectorMetadata, ConnectorTool, OAuthVersion
from agents.connectors.core.mcp_connector import MCPConfig, MCPConnector
from agents.connectors.core.mcp_tools import create_mcp_langchain_tools
from langchain.tools import BaseTool

logger = structlog.get_logger(__name__)


class GenericMCPConnector(MCPConnector):
    """
    Generic MCP Connector that can be configured dynamically.
    
    This allows users to add any MCP-compatible server through the UI
    without needing to write code.
    """
    
    def __init__(self, config: MCPConfig, redis_storage, custom_metadata: Optional[Dict[str, Any]] = None):
        """Initialize with custom metadata from user input"""
        super().__init__(config, redis_storage)
        self.custom_metadata = custom_metadata or {}
    
    def _get_metadata(self) -> ConnectorMetadata:
        """Generate metadata from user-provided configuration"""
        # Use custom metadata if provided, otherwise generate from config
        provider_id = self.custom_metadata.get("provider_id", self.mcp_config.provider_id)
        name = self.custom_metadata.get("name", f"Custom MCP: {provider_id}")
        description = self.custom_metadata.get("description", f"MCP connector for {name}")
        icon_url = self.custom_metadata.get("icon_url", "")
        
        return ConnectorMetadata(
            provider_id=provider_id,
            name=name,
            description=description,
            icon_url=icon_url,
            oauth_version=OAuthVersion.OAUTH2_0,
            available_tools=[],  # Tools discovered dynamically from MCP server
            dynamic_tools=True  # Flag indicating tools are discovered at runtime
        )
    
    def _get_mcp_server_info(self) -> Dict[str, Any]:
        """Get MCP server information"""
        return {
            "server_url": self.mcp_config.mcp_server_url,
            "server_type": "generic-mcp",
            "transport": self.mcp_config.transport_type,
            "oauth_enabled": self.mcp_config.use_remote_oauth,
            "custom": True
        }
    
    async def discover_tools(self) -> List[ConnectorTool]:
        """
        Discover available tools from the MCP server dynamically.
        
        This queries the MCP server for its capabilities and tool definitions.
        """
        try:
            mcp_tools = await self.get_mcp_tools()
            
            connector_tools = []
            for tool in mcp_tools:
                connector_tool = ConnectorTool(
                    id=tool.get("name", "unknown"),
                    name=tool.get("name", "Unknown Tool"),
                    description=tool.get("description", "No description"),
                    parameters_schema=tool.get("inputSchema", {})
                )
                connector_tools.append(connector_tool)
            
            logger.info(
                "Discovered MCP tools",
                server_url=self.mcp_config.mcp_server_url,
                num_tools=len(connector_tools)
            )
            
            return connector_tools
            
        except Exception as e:
            logger.error(
                "Failed to discover MCP tools",
                server_url=self.mcp_config.mcp_server_url,
                error=str(e)
            )
            return []
    
    async def create_langchain_tools(
        self,
        user_id: str,
        tool_ids: List[str]
    ) -> List[BaseTool]:
        """
        Create LangChain tools dynamically from MCP server.
        
        This discovers tools at runtime and creates wrappers.
        """
        token = await self.get_user_token(user_id, auto_refresh=True)
        if not token:
            logger.warning("No token found for user", user_id=user_id)
            return []
        
        # Test MCP connection
        if not await self.test_mcp_connection(user_id):
            logger.error(
                "Cannot connect to MCP server",
                user_id=user_id,
                server_url=self.mcp_config.mcp_server_url
            )
            return []
        
        # Use the generic MCP tool creation
        # This discovers tools dynamically from the server
        tools = create_mcp_langchain_tools(
            mcp_connector=self,
            user_id=user_id,
            tool_ids=tool_ids
        )
        
        logger.info(
            "Created generic MCP tools",
            user_id=user_id,
            server_url=self.mcp_config.mcp_server_url,
            num_tools=len(tools),
            tool_ids=tool_ids
        )
        
        return tools


def create_generic_mcp_connector(
    name: str,
    description: str,
    mcp_server_url: str,
    oauth_config: Dict[str, Any],
    redis_storage: Any,
    icon_url: Optional[str] = None,
    user_id: Optional[str] = None
) -> GenericMCPConnector:
    """
    Factory function to create a generic MCP connector from user input.
    
    This is what the UI calls when a user adds a custom MCP connector.
    
    IMPORTANT: Only remote SSE/HTTP MCP servers are supported.
    No local MCP installations allowed.
    
    Args:
        name: Display name for the connector
        description: User-friendly description
        mcp_server_url: URL of the REMOTE MCP server (SSE/HTTP endpoint only)
        oauth_config: OAuth configuration dict with client_id, client_secret, etc.
        redis_storage: Redis storage instance
        icon_url: Optional icon URL for the connector
        user_id: User ID for user-specific configuration
    
    Returns:
        Configured GenericMCPConnector instance
    """
    # Validate that URL is remote (not localhost)
    if any(blocked in mcp_server_url.lower() for blocked in ["localhost", "127.0.0.1", "0.0.0.0", "::1"]):
        raise ValueError("Local MCP servers are not allowed. Please use a remote SSE/HTTP endpoint.")
    
    # Generate a user-specific provider_id
    base_name = name.lower().replace(" ", "_").replace("-", "_")
    provider_id = f"custom_mcp_{base_name}"
    if user_id:
        provider_id = f"{user_id}_{provider_id}"
    
    # Build MCP config
    mcp_config = MCPConfig(
        provider_id=provider_id,
        mcp_server_url=mcp_server_url,
        transport_type="sse",  # Default to SSE for user-added connectors
        use_remote_oauth=True,
        **oauth_config
    )
    
    # Build custom metadata
    custom_metadata = {
        "provider_id": provider_id,
        "name": name,
        "description": description,
        "icon_url": icon_url or ""
    }
    
    return GenericMCPConnector(
        config=mcp_config,
        redis_storage=redis_storage,
        custom_metadata=custom_metadata
    )