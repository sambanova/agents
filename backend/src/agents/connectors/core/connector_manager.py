"""
Connector Manager for User-Level OAuth Connector Management

Handles:
- User-specific connector enablement/disablement
- Tool selection per user per connector
- Token lifecycle management per user
- Dynamic tool injection into agent runtime
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import structlog
from agents.connectors.core.base_connector import (
    BaseOAuthConnector,
    ConnectorMetadata,
    ConnectorStatus,
    ConnectorTool,
    UserConnectorConfig,
    UserOAuthToken,
)
from agents.storage.redis_storage import RedisStorage
from langchain.tools import BaseTool

logger = structlog.get_logger(__name__)


class ConnectorManager:
    """
    Manages OAuth connectors at the user level
    """
    
    def __init__(self, redis_storage: RedisStorage):
        self.redis_storage = redis_storage
        self.connectors: Dict[str, BaseOAuthConnector] = {}
        self._user_tool_cache: Dict[str, List[BaseTool]] = {}  # user_id:provider -> tools
        self._cache_ttl = 300  # 5 minutes
        self._cache_expiry: Dict[str, datetime] = {}
        # User-specific custom MCP connectors
        self._user_custom_connectors: Dict[str, Dict[str, BaseOAuthConnector]] = {}  # user_id -> {provider_id: connector}
    
    def register_connector(self, provider_id: str, connector: BaseOAuthConnector) -> None:
        """Register a connector at the system level"""
        self.connectors[provider_id] = connector
        logger.info(
            "Registered connector",
            provider=provider_id,
            tools_count=len(connector.metadata.available_tools)
        )
    
    async def get_user_connectors(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all connectors and their status for a user
        
        Returns list of connector info with user-specific status
        """
        result = []
        
        # Load user's custom MCP connectors first
        await self.load_user_custom_mcp_connectors(user_id)
        
        # Get all system connectors
        for provider_id, connector in self.connectors.items():
            # Get user-specific configuration
            config_key = f"user:{user_id}:connector:{provider_id}:config"
            config_data = await self.redis_storage.redis_client.get(config_key, user_id)
            
            if config_data:
                user_config = UserConnectorConfig(**json.loads(config_data))
            else:
                user_config = UserConnectorConfig(
                    user_id=user_id,
                    provider_id=provider_id,
                    status=ConnectorStatus.NOT_CONFIGURED
                )
            
            # Check actual connection status
            status = await connector.get_user_connector_status(user_id)
            
            # Get enabled tools for this user
            enabled_tools = await connector.get_user_enabled_tools(user_id)
            
            # Get enabled_in_chat setting from config
            enabled_in_chat = True  # Default to enabled
            if config_data:
                config_dict = json.loads(config_data)
                enabled_in_chat = config_dict.get("enabled_in_chat", True)

            result.append({
                "provider_id": provider_id,
                "name": connector.metadata.name,
                "description": connector.metadata.description,
                "icon_url": connector.metadata.icon_url,
                "status": status.value,
                "enabled": user_config.enabled,
                "enabled_in_chat": enabled_in_chat,
                "connected_at": user_config.connected_at.isoformat() if user_config.connected_at else None,
                "last_used": user_config.last_used.isoformat() if user_config.last_used else None,
                "available_tools": [
                    {
                        "id": tool.id,
                        "name": tool.name,
                        "description": tool.description,
                        "enabled": tool.id in user_config.enabled_tools
                    }
                    for tool in connector.metadata.available_tools
                ],
                "enabled_tools_count": len(enabled_tools),
                "total_tools_count": len(connector.metadata.available_tools)
            })
        
        # Add user-specific custom MCP connectors
        if user_id in self._user_custom_connectors:
            for provider_id, connector in self._user_custom_connectors[user_id].items():
                # Get user-specific configuration
                config_key = f"user:{user_id}:connector:{provider_id}:config"
                config_data = await self.redis_storage.redis_client.get(config_key, user_id)
                
                if config_data:
                    user_config = UserConnectorConfig(**json.loads(config_data))
                else:
                    user_config = UserConnectorConfig(
                        user_id=user_id,
                        provider_id=provider_id,
                        enabled=False,
                        enabled_tools=[]
                    )
                
                # Get OAuth status
                status = await connector.get_user_connector_status(user_id)
                token = await connector.get_user_token(user_id)
                
                # For custom MCP, discover tools dynamically if connected
                available_tools = []
                if status == ConnectorStatus.CONNECTED and hasattr(connector, 'discover_tools'):
                    try:
                        discovered = await connector.discover_tools()
                        available_tools = discovered
                    except:
                        pass  # Tools will be empty if discovery fails
                
                enabled_tools = user_config.enabled_tools if user_config.enabled else []

                # Get enabled_in_chat setting from config
                enabled_in_chat = True  # Default to enabled
                if config_data:
                    config_dict = json.loads(config_data)
                    enabled_in_chat = config_dict.get("enabled_in_chat", True)

                result.append({
                    "provider_id": provider_id,
                    "name": connector.metadata.name,
                    "description": connector.metadata.description,
                    "icon_url": connector.metadata.icon_url,
                    "status": status.value,
                    "enabled": user_config.enabled,
                    "enabled_in_chat": enabled_in_chat,
                    "is_custom_mcp": True,  # Flag to indicate this is a user-added MCP connector
                    "requires_auth": status != ConnectorStatus.CONNECTED,
                    "has_refresh_token": token.refresh_token is not None if token else False,
                    "tools": [
                        {
                            "id": tool.id,
                            "name": tool.name,
                            "description": tool.description,
                            "enabled": tool.id in user_config.enabled_tools
                        }
                        for tool in available_tools
                    ],
                    "enabled_tools_count": len(enabled_tools),
                    "total_tools_count": len(available_tools)
                })
        
        return result
    
    async def get_user_connector(self, user_id: str, provider_id: str) -> Optional[Dict[str, Any]]:
        """Get specific connector info for a user"""
        if provider_id not in self.connectors:
            return None
        
        connectors = await self.get_user_connectors(user_id)
        return next((c for c in connectors if c["provider_id"] == provider_id), None)
    
    async def enable_user_connector(self, user_id: str, provider_id: str) -> bool:
        """Enable a connector for a user (requires authentication first)"""
        if provider_id not in self.connectors:
            raise ValueError(f"Unknown connector: {provider_id}")
        
        connector = self.connectors[provider_id]
        
        # Check if user has valid token
        status = await connector.get_user_connector_status(user_id)
        if status not in [ConnectorStatus.CONNECTED, ConnectorStatus.EXPIRED]:
            raise ValueError("Connector not authenticated. Please complete OAuth flow first.")
        
        # Update user config
        config_key = f"user:{user_id}:connector:{provider_id}:config"
        config_data = await self.redis_storage.redis_client.get(config_key, user_id)
        config_dict = json.loads(config_data) if config_data else {}
        
        # Remove user_id and provider_id from config_dict to avoid duplicate keyword arguments
        config_dict.pop('user_id', None)
        config_dict.pop('provider_id', None)
        
        user_config = UserConnectorConfig(
            user_id=user_id,
            provider_id=provider_id,
            **config_dict
        )
        user_config.enabled = True
        user_config.status = status
        
        await self.redis_storage.redis_client.set(
            config_key, 
            json.dumps(user_config.model_dump(mode='json')), 
            user_id
        )
        
        # Invalidate cache
        self._invalidate_user_cache(user_id, provider_id)
        
        logger.info(
            "Enabled connector for user",
            user_id=user_id,
            provider=provider_id
        )
        
        return True
    
    async def disable_user_connector(self, user_id: str, provider_id: str) -> bool:
        """Disable a connector for a user (keeps authentication)"""
        if provider_id not in self.connectors:
            raise ValueError(f"Unknown connector: {provider_id}")
        
        # Update user config
        config_key = f"user:{user_id}:connector:{provider_id}:config"
        config_data = await self.redis_storage.redis_client.get(config_key, user_id)
        config_dict = json.loads(config_data) if config_data else {}
        
        # Remove user_id and provider_id from config_dict to avoid duplicate keyword arguments
        config_dict.pop('user_id', None)
        config_dict.pop('provider_id', None)
        
        user_config = UserConnectorConfig(
            user_id=user_id,
            provider_id=provider_id,
            **config_dict
        )
        user_config.enabled = False
        
        await self.redis_storage.redis_client.set(
            config_key, 
            json.dumps(user_config.model_dump(mode='json')), 
            user_id
        )
        
        # Invalidate cache
        self._invalidate_user_cache(user_id, provider_id)
        
        logger.info(
            "Disabled connector for user",
            user_id=user_id,
            provider=provider_id
        )
        
        return True
    
    async def disconnect_user_connector(self, user_id: str, provider_id: str) -> bool:
        """Completely disconnect and revoke user's connector access"""
        if provider_id not in self.connectors:
            raise ValueError(f"Unknown connector: {provider_id}")
        
        connector = self.connectors[provider_id]
        
        # Revoke token
        await connector.revoke_user_token(user_id)
        
        # Clear user config
        config_key = f"user:{user_id}:connector:{provider_id}:config"
        await self.redis_storage.redis_client.delete(config_key)
        
        # Invalidate cache
        self._invalidate_user_cache(user_id, provider_id)
        
        logger.info(
            "Disconnected connector for user",
            user_id=user_id,
            provider=provider_id
        )
        
        return True
    
    async def update_user_tools(
        self, 
        user_id: str, 
        provider_id: str, 
        enabled_tool_ids: Set[str]
    ) -> bool:
        """Update which tools a user has enabled for a connector"""
        if provider_id not in self.connectors:
            raise ValueError(f"Unknown connector: {provider_id}")
        
        connector = self.connectors[provider_id]
        
        # Validate tool IDs
        available_tool_ids = {tool.id for tool in connector.metadata.available_tools}
        invalid_tools = enabled_tool_ids - available_tool_ids
        if invalid_tools:
            raise ValueError(f"Invalid tool IDs: {invalid_tools}")
        
        # Update user config
        await connector.set_user_enabled_tools(user_id, enabled_tool_ids)
        
        # Invalidate cache
        self._invalidate_user_cache(user_id, provider_id)
        
        logger.info(
            "Updated user tools",
            user_id=user_id,
            provider=provider_id,
            enabled_count=len(enabled_tool_ids)
        )
        
        return True
    
    async def get_user_tools(self, user_id: str, force_refresh: bool = False) -> List[BaseTool]:
        """
        Get all enabled tools for a user across all connectors
        
        This is the main method used by the agent runtime to get user's tools
        """
        # Check cache
        cache_key = f"{user_id}:all"
        if not force_refresh and self._is_cache_valid(cache_key):
            cached_tools = self._user_tool_cache.get(cache_key, [])
            if cached_tools:
                logger.debug(
                    "Using cached tools",
                    user_id=user_id,
                    count=len(cached_tools)
                )
                return cached_tools
        
        all_tools = []

        logger.info(
            "Getting user tools - starting",
            user_id=user_id,
            num_connectors=len(self.connectors)
        )

        # Iterate through all connectors
        for provider_id, connector in self.connectors.items():
            try:
                # Check if connector is enabled for user
                config_key = f"user:{user_id}:connector:{provider_id}:config"
                config_data = await self.redis_storage.redis_client.get(config_key, user_id)

                if not config_data:
                    logger.info(
                        "No config found for connector",
                        user_id=user_id,
                        provider=provider_id
                    )
                    continue

                config_dict = json.loads(config_data)

                # Log the raw config to see what's stored
                logger.info(
                    "Raw connector config",
                    user_id=user_id,
                    provider=provider_id,
                    config=config_dict
                )

                user_config = UserConnectorConfig(**config_dict)

                if not user_config.enabled:
                    logger.info(
                        "Connector not enabled",
                        user_id=user_id,
                        provider=provider_id
                    )
                    continue

                # Check if connector is enabled in chat context
                enabled_in_chat = config_dict.get("enabled_in_chat", True)
                if not enabled_in_chat:
                    logger.info(
                        "Connector disabled in chat context",
                        user_id=user_id,
                        provider=provider_id
                    )
                    continue

                # Get token with automatic refresh
                token = await connector.get_user_token(user_id, auto_refresh=True)
                if not token:
                    logger.warning(
                        "No valid token available for connector",
                        user_id=user_id,
                        provider=provider_id
                    )
                    continue

                logger.info(
                    "Token available for connector",
                    user_id=user_id,
                    provider=provider_id
                )

                # Get enabled tools for this connector
                enabled_tools = await connector.get_user_enabled_tools(user_id)

                logger.info(
                    "Enabled tools for connector",
                    user_id=user_id,
                    provider=provider_id,
                    num_enabled_tools=len(enabled_tools) if enabled_tools else 0,
                    tool_ids=[tool.id for tool in enabled_tools] if enabled_tools else []
                )
                
                # Check if connector supports batch LangChain tool creation
                if hasattr(connector, 'create_langchain_tools') and enabled_tools:
                    # Batch create all tools at once for efficiency
                    tool_ids = [tool.id for tool in enabled_tools]
                    try:
                        langchain_tools = await connector.create_langchain_tools(user_id, tool_ids)
                        if langchain_tools:
                            all_tools.extend(langchain_tools)
                            logger.info(
                                "Batch created LangChain tools",
                                user_id=user_id,
                                provider=provider_id,
                                count=len(langchain_tools)
                            )
                    except Exception as e:
                        logger.error(
                            "Failed to batch create LangChain tools",
                            user_id=user_id,
                            provider=provider_id,
                            error=str(e)
                        )
                        # Fall back to individual creation
                        for tool in enabled_tools:
                            langchain_tool = await self._create_langchain_tool(
                                user_id,
                                provider_id,
                                tool
                            )
                            if langchain_tool:
                                all_tools.append(langchain_tool)
                else:
                    # Convert to LangChain tools individually
                    for tool in enabled_tools:
                        langchain_tool = await self._create_langchain_tool(
                            user_id,
                            provider_id,
                            tool
                        )
                        if langchain_tool:
                            all_tools.append(langchain_tool)
                
            except Exception as e:
                logger.error(
                    "Error loading tools from connector",
                    user_id=user_id,
                    provider=provider_id,
                    error=str(e)
                )
                continue
        
        # Cache the results
        self._user_tool_cache[cache_key] = all_tools
        self._cache_expiry[cache_key] = datetime.utcnow()
        
        logger.info(
            "Loaded user tools",
            user_id=user_id,
            total_tools=len(all_tools)
        )
        
        return all_tools
    
    async def refresh_user_tokens(self, user_id: str) -> Dict[str, bool]:
        """
        Refresh all expired tokens for a user
        
        Returns dict of provider_id -> success status
        """
        results = {}
        
        for provider_id, connector in self.connectors.items():
            try:
                token = await connector.get_user_token(user_id)
                if token and token.needs_refresh:
                    await connector.refresh_user_token(user_id)
                    results[provider_id] = True
                else:
                    results[provider_id] = False  # No refresh needed
            except Exception as e:
                logger.error(
                    "Failed to refresh token",
                    user_id=user_id,
                    provider=provider_id,
                    error=str(e)
                )
                results[provider_id] = False
        
        return results
    
    async def load_user_custom_mcp_connectors(self, user_id: str) -> None:
        """
        Load user-specific custom MCP connectors from Redis.
        
        This is called when a user's tools are requested to ensure
        their custom MCP connectors are available.
        """
        try:
            # Get all custom MCP connectors for this user
            pattern = f"user:{user_id}:custom_mcp:*"
            keys = await self.redis_storage.redis_client.keys(pattern)
            
            if user_id not in self._user_custom_connectors:
                self._user_custom_connectors[user_id] = {}
            
            for key in keys:
                data = await self.redis_storage.redis_client.get(key)
                if data:
                    connector_data = json.loads(data)
                    provider_id = connector_data["provider_id"]
                    
                    # Check if we already have this connector loaded
                    if provider_id not in self._user_custom_connectors[user_id]:
                        # Import here to avoid circular dependency
                        from agents.connectors.providers.generic_mcp import create_generic_mcp_connector
                        
                        # Create the connector instance
                        connector = create_generic_mcp_connector(
                            name=connector_data["name"],
                            description=connector_data.get("description", ""),
                            mcp_server_url=connector_data["mcp_server_url"],
                            oauth_config=connector_data["oauth_config"],
                            redis_storage=self.redis_storage,
                            icon_url=connector_data.get("icon_url"),
                            user_id=user_id
                        )
                        
                        # Store in user-specific connector map
                        self._user_custom_connectors[user_id][provider_id] = connector
                        
                        logger.info(
                            "Loaded custom MCP connector",
                            user_id=user_id,
                            provider_id=provider_id,
                            name=connector_data["name"]
                        )
            
        except Exception as e:
            logger.error(
                "Failed to load custom MCP connectors",
                user_id=user_id,
                error=str(e),
                exc_info=True
            )
    
    def get_connector_for_user(self, user_id: str, provider_id: str) -> Optional[BaseOAuthConnector]:
        """
        Get a connector for a specific user.
        
        Checks both system-level and user-specific connectors.
        """
        # First check user-specific custom connectors
        if user_id in self._user_custom_connectors:
            if provider_id in self._user_custom_connectors[user_id]:
                return self._user_custom_connectors[user_id][provider_id]
        
        # Fall back to system-level connectors
        return self.connectors.get(provider_id)
    
    async def _create_langchain_tool(
        self,
        user_id: str,
        provider_id: str,
        tool: ConnectorTool
    ) -> Optional[BaseTool]:
        """
        Create a LangChain tool from a connector tool
        
        This is where connector tools are converted to agent-usable tools
        """
        try:
            # Get connector (user-specific or system-level)
            connector = self.get_connector_for_user(user_id, provider_id)
            if not connector:
                return None
            
            # Check if connector has a method to create LangChain tools
            if hasattr(connector, 'create_langchain_tools'):
                # Get the specific tool
                tools = await connector.create_langchain_tools(user_id, [tool.id])
                if tools:
                    return tools[0]  # Return the first (and only) tool
            
            logger.debug(
                "Connector doesn't support LangChain tool creation",
                user_id=user_id,
                provider=provider_id,
                tool_id=tool.id
            )
            return None
            
        except Exception as e:
            logger.error(
                "Failed to create LangChain tool",
                user_id=user_id,
                provider=provider_id,
                tool_id=tool.id,
                error=str(e)
            )
            return None
    
    def _invalidate_user_cache(self, user_id: str, provider_id: Optional[str] = None) -> None:
        """Invalidate tool cache for a user"""
        if provider_id:
            cache_key = f"{user_id}:{provider_id}"
            if cache_key in self._user_tool_cache:
                del self._user_tool_cache[cache_key]
            if cache_key in self._cache_expiry:
                del self._cache_expiry[cache_key]
        
        # Always invalidate the "all" cache
        cache_key = f"{user_id}:all"
        if cache_key in self._user_tool_cache:
            del self._user_tool_cache[cache_key]
        if cache_key in self._cache_expiry:
            del self._cache_expiry[cache_key]
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache is still valid"""
        if cache_key not in self._cache_expiry:
            return False
        
        expiry = self._cache_expiry[cache_key]
        elapsed = (datetime.utcnow() - expiry).total_seconds()
        return elapsed < self._cache_ttl
    
    async def get_system_connectors(self) -> List[ConnectorMetadata]:
        """Get all available connectors at the system level"""
        return [connector.metadata for connector in self.connectors.values()]


# Global instance
_connector_manager: Optional[ConnectorManager] = None


def get_connector_manager() -> Optional[ConnectorManager]:
    """Get the global connector manager instance"""
    return _connector_manager


def set_connector_manager(manager: ConnectorManager) -> None:
    """Set the global connector manager instance"""
    global _connector_manager
    _connector_manager = manager


async def get_user_connector_tools(user_id: str, force_refresh: bool = False) -> List[BaseTool]:
    """
    Convenience function to get user's connector tools
    
    This integrates with your existing dynamic_tool_loader
    """
    manager = get_connector_manager()
    if not manager:
        logger.warning("Connector manager not initialized")
        return []
    
    return await manager.get_user_tools(user_id, force_refresh)