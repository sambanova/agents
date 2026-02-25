"""
Dynamic MCP Connector Routes

API endpoints for users to add custom MCP connectors via UI.
"""

import json
from typing import Optional

import structlog
from agents.connectors.core.connector_manager import ConnectorManager
from agents.connectors.providers.generic_mcp import create_generic_mcp_connector
from agents.storage.redis_storage import RedisStorage
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from agents.api.utils import validate_external_url
from agents.auth.auth0_config import get_current_user_id

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/dynamic-mcp", tags=["dynamic-mcp"])


class AddMCPConnectorRequest(BaseModel):
    """Request to add a custom MCP connector
    
    MCP servers handle their own OAuth through discovery.
    We only need the server URL - no credentials required.
    """
    name: str = Field(..., description="Display name for the connector")
    description: Optional[str] = Field(None, description="Description of the connector")
    mcp_server_url: HttpUrl = Field(..., description="URL of the remote MCP server (SSE/HTTP endpoint)")
    icon_url: Optional[HttpUrl] = Field(None, description="Icon URL for the connector")


class MCPConnectorResponse(BaseModel):
    """Response after adding an MCP connector"""
    provider_id: str
    name: str
    description: str
    mcp_server_url: str
    status: str
    message: str


@router.post("/add", response_model=MCPConnectorResponse)
async def add_mcp_connector(
    request: AddMCPConnectorRequest,
    user_id: str = Depends(get_current_user_id),
    connector_manager: ConnectorManager = Depends(lambda: ConnectorManager.get_instance()),
    redis_storage: RedisStorage = Depends(lambda: RedisStorage.get_instance())
):
    """
    Add a custom MCP connector for the current user.
    
    This allows users to add any MCP-compatible server through the API.
    """
    
    # SSRF protection: block internal/private URLs
    if not validate_external_url(str(request.mcp_server_url)):
        raise HTTPException(
            status_code=400,
            detail="Invalid MCP server URL: must be an external, publicly-routable address"
        )
    if request.icon_url and not validate_external_url(str(request.icon_url)):
        raise HTTPException(
            status_code=400,
            detail="Invalid icon URL: must be an external, publicly-routable address"
        )

    try:
        # Generate provider_id from name
        provider_id = request.name.lower().replace(" ", "_").replace("-", "_")
        provider_id = f"custom_mcp_{provider_id}"
        
        logger.info(
            "Adding custom MCP connector",
            user_id=user_id,
            provider_id=provider_id,
            name=request.name,
            mcp_server_url=str(request.mcp_server_url)
        )
        
        # MCP servers handle their own OAuth - minimal config needed
        # OAuth details will be discovered from the MCP server
        oauth_config = {
            "client_id": "",  # Will be handled by MCP server
            "client_secret": "",  # Will be handled by MCP server
            "authorization_url": "",  # Will be discovered
            "token_url": "",  # Will be discovered
            "redirect_uri": f"http://localhost:8000/api/connectors/{provider_id}/callback"
        }
        
        # Create the generic MCP connector
        connector = create_generic_mcp_connector(
            name=request.name,
            description=request.description or f"Custom MCP connector for {request.name}",
            mcp_server_url=str(request.mcp_server_url),
            oauth_config=oauth_config,
            redis_storage=redis_storage,
            icon_url=str(request.icon_url) if request.icon_url else None
        )
        
        # Register the connector with the manager
        connector_manager.register_connector(provider_id, connector)
        
        # Store the custom connector configuration for the user
        # This allows it to be loaded on restart
        custom_connector_key = f"user:{user_id}:custom_mcp:{provider_id}"
        custom_connector_data = {
            "provider_id": provider_id,
            "name": request.name,
            "description": request.description,
            "mcp_server_url": str(request.mcp_server_url),
            "icon_url": str(request.icon_url) if request.icon_url else None,
            "oauth_config": oauth_config,
            "created_by": user_id,
            "enabled": True
        }
        
        await redis_storage.redis_client.set(
            custom_connector_key,
            json.dumps(custom_connector_data)
        )
        
        # Try to discover tools from the MCP server
        try:
            tools = await connector.discover_tools()
            logger.info(
                "Discovered tools from custom MCP server",
                provider_id=provider_id,
                num_tools=len(tools)
            )
        except Exception as e:
            logger.warning(
                "Could not discover tools (server may require auth)",
                provider_id=provider_id,
                error=str(e)
            )
        
        return MCPConnectorResponse(
            provider_id=provider_id,
            name=request.name,
            description=request.description or "",
            mcp_server_url=str(request.mcp_server_url),
            status="success",
            message=f"Successfully added MCP connector '{request.name}'"
        )
        
    except Exception as e:
        logger.error(
            "Failed to add custom MCP connector",
            user_id=user_id,
            name=request.name,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred"
        )


@router.get("/list")
async def list_custom_mcp_connectors(
    user_id: str = Depends(get_current_user_id),
    redis_storage: RedisStorage = Depends(lambda: RedisStorage.get_instance())
):
    """
    List all custom MCP connectors for the current user.
    """
    
    try:
        # Get all custom MCP connectors for this user
        pattern = f"user:{user_id}:custom_mcp:*"
        keys = await redis_storage.redis_client.keys(pattern)
        
        connectors = []
        for key in keys:
            data = await redis_storage.redis_client.get(key)
            if data:
                connector_data = json.loads(data)
                connectors.append({
                    "provider_id": connector_data["provider_id"],
                    "name": connector_data["name"],
                    "description": connector_data.get("description", ""),
                    "mcp_server_url": connector_data["mcp_server_url"],
                    "icon_url": connector_data.get("icon_url", ""),
                    "enabled": connector_data.get("enabled", True)
                })
        
        return {"connectors": connectors}
        
    except Exception as e:
        logger.error(
            "Failed to list custom MCP connectors",
            user_id=user_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred"
        )


@router.delete("/{provider_id}")
async def remove_custom_mcp_connector(
    provider_id: str,
    user_id: str = Depends(get_current_user_id),
    redis_storage: RedisStorage = Depends(lambda: RedisStorage.get_instance()),
    connector_manager: ConnectorManager = Depends(lambda: ConnectorManager.get_instance())
):
    """
    Remove a custom MCP connector.
    """
    
    try:
        # Remove from Redis
        custom_connector_key = f"user:{user_id}:custom_mcp:{provider_id}"
        deleted = await redis_storage.redis_client.delete(custom_connector_key)
        
        if deleted == 0:
            raise HTTPException(
                status_code=404,
                detail=f"MCP connector '{provider_id}' not found"
            )
        
        # Unregister from connector manager if loaded
        # Note: This only affects the current instance
        # TODO: Implement proper multi-instance synchronization
        
        return {
            "status": "success",
            "message": f"Successfully removed MCP connector '{provider_id}'"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to remove custom MCP connector",
            user_id=user_id,
            provider_id=provider_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred"
        )