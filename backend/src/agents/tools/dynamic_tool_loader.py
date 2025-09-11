"""
Dynamic tool loading system that merges static tools with user-specific connector tools.

This module provides functionality to load and combine tools from the static tool registry
with dynamically discovered connector tools for each user.
"""

import asyncio
from typing import Any, Dict, List, Optional, Sequence, Union

import structlog
from agents.storage.redis_storage import RedisStorage
from agents.tools.langgraph_tools import TOOL_REGISTRY, Tool as StaticToolConfig, validate_tool_config
from langchain.tools import BaseTool

logger = structlog.get_logger(__name__)


class DynamicToolLoader:
    """
    Loads and manages both static and connector tools for users.
    
    This class handles the integration of static tools from the TOOL_REGISTRY
    with user-specific connector tools from their configured OAuth connectors.
    """

    def __init__(self, redis_storage: Optional[RedisStorage], connector_manager: Optional[Any] = None):
        self.redis_storage = redis_storage
        self.connector_manager = connector_manager
        self.tool_cache: Dict[str, List[BaseTool]] = {}  # user_id -> cached tools
        self.cache_expiry: Dict[str, float] = {}  # user_id -> expiry time
        self.cache_ttl = 300  # 5 minutes cache TTL

    async def load_user_tools(
        self,
        user_id: str,
        static_tools: Sequence[StaticToolConfig],
        force_refresh: bool = False,
    ) -> List[BaseTool]:
        """
        Load both static and connector tools for a user.
        
        Args:
            user_id: The user ID to load tools for
            static_tools: List of static tool configurations
            force_refresh: Whether to force refresh the tool cache
            
        Returns:
            List of all tools (static + connector) for the user
        """
        try:
            # Check cache first
            if not force_refresh and self._is_user_cache_valid(user_id):
                cached_tools = self.tool_cache.get(user_id, [])
                if cached_tools:
                    logger.info(
                        "Using cached tools for user",
                        user_id=user_id,
                        num_tools=len(cached_tools),
                    )
                    return cached_tools

            # Load static tools
            static_tool_instances = await self._load_static_tools(static_tools)
            
            # Load connector tools for the user
            connector_tool_instances = await self._load_connector_tools(user_id)
            
            # Combine all tools
            all_tools = static_tool_instances + connector_tool_instances
            
            # Cache the result
            self.tool_cache[user_id] = all_tools
            self.cache_expiry[user_id] = asyncio.get_event_loop().time() + self.cache_ttl
            
            logger.info(
                "Loaded tools for user",
                user_id=user_id,
                num_static_tools=len(static_tool_instances),
                num_connector_tools=len(connector_tool_instances),
                total_tools=len(all_tools),
            )
            
            return all_tools
            
        except Exception as e:
            logger.error(
                "Error loading user tools",
                user_id=user_id,
                error=str(e),
                exc_info=True,
            )
            # Fall back to just static tools
            return await self._load_static_tools(static_tools)

    async def reload_user_connector_tools(self, user_id: str) -> None:
        """
        Reload connector tools for a user and invalidate cache.
        
        This is useful when a user adds/removes/updates OAuth connectors.
        """
        try:
            # Invalidate cache
            if user_id in self.tool_cache:
                del self.tool_cache[user_id]
            if user_id in self.cache_expiry:
                del self.cache_expiry[user_id]
            
            # Reload connector tools if needed
            if self.connector_manager is not None:
                # Force refresh connector tools
                await self.connector_manager.get_user_tools(user_id, force_refresh=True)
            
            logger.info("Reloaded connector tools for user", user_id=user_id)
            
        except Exception as e:
            logger.error(
                "Error reloading connector tools for user",
                user_id=user_id,
                error=str(e),
                exc_info=True,
            )

    async def get_user_tool_info(self, user_id: str) -> Dict[str, Any]:
        """
        Get information about a user's available tools.
        
        Returns:
            Dictionary with tool information including counts and server status
        """
        try:
            # Check if services are available
            if self.redis_storage is None or self.connector_manager is None:
                logger.info("Connector services not available for user tool info")
                return {
                    "total_connectors": 0,
                    "enabled_connectors": 0,
                    "available_connector_tools": 0,
                    "cached_tools": len(self.tool_cache.get(user_id, [])),
                    "cache_valid": self._is_user_cache_valid(user_id),
                    "connectors": [],
                }
            
            # Get connector info
            connector_tools = await self.connector_manager.get_user_tools(user_id)
            
            # Get connector status info from manager if available
            connector_info = []
            if hasattr(self.connector_manager, 'get_user_connectors_info'):
                connector_info = await self.connector_manager.get_user_connectors_info(user_id)
            
            # Get cached tools if available
            cached_tools = self.tool_cache.get(user_id, [])
            
            return {
                "total_connectors": len(connector_info),
                "available_connector_tools": len(connector_tools),
                "cached_tools": len(cached_tools),
                "cache_valid": self._is_user_cache_valid(user_id),
                "connectors": connector_info,
            }
            
        except Exception as e:
            logger.error(
                "Error getting user tool info",
                user_id=user_id,
                error=str(e),
                exc_info=True,
            )
            return {
                "total_connectors": 0,
                "available_connector_tools": 0,
                "cached_tools": 0,
                "cache_valid": False,
                "connectors": [],
            }

    def invalidate_user_cache(self, user_id: str) -> None:
        """Invalidate the tool cache for a specific user."""
        if user_id in self.tool_cache:
            del self.tool_cache[user_id]
        if user_id in self.cache_expiry:
            del self.cache_expiry[user_id]
        logger.info("Invalidated tool cache for user", user_id=user_id)

    def clear_all_caches(self) -> None:
        """Clear all tool caches."""
        self.tool_cache.clear()
        self.cache_expiry.clear()
        logger.info("Cleared all tool caches")

    async def _load_static_tools(self, static_tools: Sequence[StaticToolConfig]) -> List[BaseTool]:
        """Load static tools from the tool registry."""
        try:
            _tools = []
            from langchain.tools import BaseTool as _BT
            from pydantic import BaseModel
            
            for _tool in static_tools:
                # If caller already provided a ready-made BaseTool instance, keep it
                if isinstance(_tool, _BT):
                    _tools.append(_tool)
                    continue

                # Handle Pydantic model instances (like Arxiv, Tavily, etc.)
                if isinstance(_tool, BaseModel) and hasattr(_tool, 'type') and hasattr(_tool, 'config'):
                    tool_type = _tool.type
                    tool_config = _tool.config
                # Handle dictionary configs {"type": name, "config": {...}}
                elif isinstance(_tool, dict):
                    try:
                        tool_type = _tool["type"]
                        tool_config = _tool.get("config", {})
                    except Exception:
                        logger.error("Invalid static tool spec, skipping", tool=_tool)
                        continue
                else:
                    logger.error("Invalid static tool spec, skipping", tool=_tool)
                    continue

                try:
                    validated_config = validate_tool_config(tool_type, tool_config)
                except ValueError as e:
                    logger.error(f"Tool validation failed: {e}")
                    continue

                _returned_tools = TOOL_REGISTRY[tool_type]["factory"](**validated_config)
                if isinstance(_returned_tools, list):
                    _tools.extend(_returned_tools)
                else:
                    _tools.append(_returned_tools)

            logger.info("Loaded static tools", num_tools=len(_tools))
            return _tools
            
        except Exception as e:
            logger.error(
                "Error loading static tools",
                error=str(e),
                exc_info=True,
            )
            return []

    async def _load_connector_tools(self, user_id: str) -> List[BaseTool]:
        """Load connector tools for a user."""
        try:
            # Check if connector manager is available
            if self.connector_manager is None:
                logger.info("Connector manager not available, skipping connector tools")
                return []
            
            # Get connector tools from the connector manager
            connector_tools = await self.connector_manager.get_user_tools(user_id)
            
            logger.info(
                "Loaded connector tools for user",
                user_id=user_id,
                num_tools=len(connector_tools),
            )
            
            return connector_tools
            
        except Exception as e:
            logger.error(
                "Error loading connector tools for user",
                user_id=user_id,
                error=str(e),
                exc_info=True,
            )
            return []

    def _is_user_cache_valid(self, user_id: str) -> bool:
        """Check if the user's tool cache is still valid."""
        if user_id not in self.cache_expiry:
            return False
        return asyncio.get_event_loop().time() < self.cache_expiry[user_id]


# Global instance to be initialized by the application
_global_dynamic_tool_loader: Optional[DynamicToolLoader] = None


def get_dynamic_tool_loader() -> Optional[DynamicToolLoader]:
    """Get the global dynamic tool loader instance."""
    return _global_dynamic_tool_loader


def set_dynamic_tool_loader(loader: DynamicToolLoader) -> None:
    """Set the global dynamic tool loader instance."""
    global _global_dynamic_tool_loader
    _global_dynamic_tool_loader = loader


async def load_tools_for_user(
    user_id: str,
    static_tools: Sequence[StaticToolConfig],
    force_refresh: bool = False,
) -> List[BaseTool]:
    """
    Convenience function to load tools for a user using the global tool loader.
    
    Args:
        user_id: The user ID to load tools for
        static_tools: List of static tool configurations
        force_refresh: Whether to force refresh the tool cache
        
    Returns:
        List of all tools (static + MCP) for the user
    """
    loader = get_dynamic_tool_loader()
    if loader is None:
        # Try to ensure connector services are initialized
        try:
            from agents.storage.global_services import ensure_connector_services_initialized
            if ensure_connector_services_initialized():
                loader = get_dynamic_tool_loader()
        except Exception as e:
            logger.warning(f"Failed to initialize connector services: {e}")
    
    if loader is None:
        logger.warning("Dynamic tool loader not initialized, loading static tools only")
        temp_loader = DynamicToolLoader(None, None)
        return await temp_loader._load_static_tools(static_tools)
    
    return await loader.load_user_tools(user_id, static_tools, force_refresh)


async def reload_connector_tools_for_user(user_id: str) -> None:
    """
    Convenience function to reload connector tools for a user using the global tool loader.
    """
    loader = get_dynamic_tool_loader()
    if loader is None:
        logger.warning("Dynamic tool loader not initialized")
        return
    
    await loader.reload_user_connector_tools(user_id) 