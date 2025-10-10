"""
OAuth Connector API Routes

Handles OAuth flows, connector management, and tool selection at the user level.
"""

import json
import os
from typing import Any, Dict, List, Optional, Set

import structlog
from agents.auth.auth0_config import get_current_user_id
from agents.connectors.core.connector_manager import get_connector_manager
from agents.connectors.core.base_connector import ConnectorStatus
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/connectors", tags=["connectors"])


class ConnectorStatusResponse(BaseModel):
    """Response for connector status"""
    provider_id: str
    name: str
    description: str
    icon_url: Optional[str]
    status: str
    enabled: bool
    enabled_in_chat: bool = True  # Whether connector is enabled for chat context
    connected_at: Optional[str]
    last_used: Optional[str]
    available_tools: List[Dict[str, Any]]
    enabled_tools_count: int
    total_tools_count: int


class UpdateToolsRequest(BaseModel):
    """Request to update enabled tools for a connector"""
    enabled_tool_ids: Set[str] = Field(default_factory=set)


class ToggleChatRequest(BaseModel):
    """Request to toggle connector availability in chat"""
    enabled: bool


class OAuthCallbackResponse(BaseModel):
    """Response after OAuth callback"""
    success: bool
    provider_id: str
    message: str
    error: Optional[str] = None


@router.get("/available", response_model=List[Dict[str, Any]])
async def get_available_connectors(user_id: str = Depends(get_current_user_id)):
    """
    Get all available connectors at the system level
    
    This returns all connectors that are configured in the system,
    regardless of user connection status.
    """
    try:
        manager = get_connector_manager()
        if not manager:
            raise HTTPException(status_code=500, detail="Connector manager not initialized")
        
        connectors = await manager.get_system_connectors()
        
        return [
            {
                "provider_id": c.provider_id,
                "name": c.name,
                "description": c.description,
                "icon_url": c.icon_url,
                "oauth_version": c.oauth_version.value,
                "available_tools_count": len(c.available_tools),
                "required_scopes": c.required_scopes,
                "optional_scopes": c.optional_scopes
            }
            for c in connectors
        ]
    except Exception as e:
        logger.error("Failed to get available connectors", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user", response_model=List[ConnectorStatusResponse])
async def get_user_connectors(user_id: str = Depends(get_current_user_id)):
    """
    Get all connectors and their status for the current user
    
    Returns connection status, enabled tools, etc. for each connector.
    """
    try:
        manager = get_connector_manager()
        if not manager:
            logger.error("Connector manager not initialized")
            raise HTTPException(status_code=500, detail="Connector manager not initialized")
        
        logger.info(
            "Getting user connectors",
            user_id=user_id,
            num_registered_connectors=len(manager.connectors)
        )
        
        connectors = await manager.get_user_connectors(user_id)
        
        logger.info(
            "Returning user connectors",
            user_id=user_id,
            num_connectors=len(connectors)
        )
        
        return connectors
    except Exception as e:
        logger.error("Failed to get user connectors", user_id=user_id, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{provider_id}", response_model=ConnectorStatusResponse)
async def get_user_connector(
    provider_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Get specific connector status for the current user"""
    try:
        manager = get_connector_manager()
        if not manager:
            raise HTTPException(status_code=500, detail="Connector manager not initialized")
        
        connector = await manager.get_user_connector(user_id, provider_id)
        if not connector:
            raise HTTPException(status_code=404, detail=f"Connector {provider_id} not found")
        
        return connector
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get connector",
            user_id=user_id,
            provider_id=provider_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{provider_id}/auth/init")
async def init_oauth_flow(
    provider_id: str,
    user_id: str = Depends(get_current_user_id),
    redirect_uri: Optional[str] = None
):
    """
    Initialize OAuth flow for a connector
    
    Returns the authorization URL to redirect the user to.
    """
    try:
        manager = get_connector_manager()
        if not manager:
            raise HTTPException(status_code=500, detail="Connector manager not initialized")
        
        if provider_id not in manager.connectors:
            raise HTTPException(status_code=404, detail=f"Connector {provider_id} not found")
        
        connector = manager.connectors[provider_id]
        
        # Generate authorization URL
        auth_url, state = await connector.get_authorization_url(user_id)
        
        # Log the full authorization URL for debugging
        logger.info(
            "Generated full authorization URL",
            provider_id=provider_id,
            auth_url=auth_url,
            user_id=user_id
        )
        
        # Store redirect URI in state if provided
        if redirect_uri:
            # This would be stored in Redis with the state
            pass
        
        return {
            "authorization_url": auth_url,
            "state": state,
            "provider_id": provider_id
        }
        
    except Exception as e:
        logger.error(
            "Failed to initialize OAuth flow",
            user_id=user_id,
            provider_id=provider_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{provider_id}/callback")
async def oauth_callback(
    provider_id: str,
    code: str = Query(...),
    state: str = Query(...),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    request: Request = None
):
    """
    OAuth callback endpoint
    
    Handles the OAuth provider redirect after user authorization.
    """
    try:
        # Handle OAuth errors
        if error:
            logger.error(
                "OAuth error",
                provider_id=provider_id,
                error=error,
                error_description=error_description
            )
            # Redirect to OAuth callback page with error
            frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
            return RedirectResponse(
                url=f"{frontend_url}/oauth-callback?error={error}&provider={provider_id}"
            )
        
        manager = get_connector_manager()
        if not manager:
            raise HTTPException(status_code=500, detail="Connector manager not initialized")
        
        if provider_id not in manager.connectors:
            raise HTTPException(status_code=404, detail=f"Connector {provider_id} not found")
        
        connector = manager.connectors[provider_id]
        
        # Get user_id from state (stored during init)
        # Retrieve state from Redis using plain Redis (OAuth state is not encrypted)
        state_key = f"oauth:state:{state}"
        
        logger.info(
            "Retrieving OAuth state",
            state_key=state_key,
            state=state[:10] + "..." if state else None
        )
        
        from redis.asyncio import Redis
        plain_redis = Redis(connection_pool=connector.redis_storage.redis_client.connection_pool, decode_responses=True)
        state_json = await plain_redis.get(state_key)
        await plain_redis.close()
        
        logger.info(
            "Retrieved OAuth state",
            state_exists=bool(state_json),
            state_length=len(state_json) if state_json else 0
        )
        
        if not state_json:
            logger.error("OAuth state not found in Redis", state_key=state_key)
            raise HTTPException(status_code=400, detail="Invalid or expired state")
        
        state_data = json.loads(state_json)
        
        user_id = state_data.get("user_id")
        
        # Exchange code for token
        token = await connector.exchange_code_for_token(code, state, user_id)
        
        # Enable connector for user
        await manager.enable_user_connector(user_id, provider_id)

        # Automatically enable ALL tools for the newly connected connector
        connector_info = await manager.get_user_connector(user_id, provider_id)
        if connector_info and connector_info.get("available_tools"):
            # Get all available tool IDs
            all_tool_ids = {tool["id"] for tool in connector_info["available_tools"]}

            # Enable all tools for this connector
            logger.info(
                "Auto-enabling all tools after OAuth",
                user_id=user_id,
                provider_id=provider_id,
                num_tools=len(all_tool_ids)
            )

            await manager.update_user_tools(user_id, provider_id, all_tool_ids)

        # Redirect to OAuth callback page which will close the popup
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        return RedirectResponse(
            url=f"{frontend_url}/oauth-callback?success=true&provider={provider_id}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "OAuth callback failed",
            provider_id=provider_id,
            error=str(e)
        )
        # Redirect to OAuth callback page with error
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        return RedirectResponse(
            url=f"{frontend_url}/oauth-callback?error=callback_failed&provider={provider_id}"
        )


@router.post("/{provider_id}/refresh")
async def refresh_connector_token(
    provider_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Refresh the OAuth token for a connector"""
    try:
        manager = get_connector_manager()
        if not manager:
            raise HTTPException(status_code=500, detail="Connector manager not initialized")
        
        if provider_id not in manager.connectors:
            raise HTTPException(status_code=404, detail=f"Connector {provider_id} not found")
        
        connector = manager.connectors[provider_id]
        token = await connector.refresh_user_token(user_id)
        
        return {
            "success": True,
            "provider_id": provider_id,
            "expires_in": token.expires_in_seconds
        }
        
    except Exception as e:
        logger.error(
            "Failed to refresh token",
            user_id=user_id,
            provider_id=provider_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{provider_id}/disconnect")
async def disconnect_connector(
    provider_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Disconnect and revoke access for a connector"""
    try:
        manager = get_connector_manager()
        if not manager:
            raise HTTPException(status_code=500, detail="Connector manager not initialized")
        
        success = await manager.disconnect_user_connector(user_id, provider_id)
        
        return {
            "success": success,
            "provider_id": provider_id,
            "message": "Connector disconnected successfully"
        }
        
    except Exception as e:
        logger.error(
            "Failed to disconnect connector",
            user_id=user_id,
            provider_id=provider_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{provider_id}/tools")
async def get_connector_tools(
    provider_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Get available and enabled tools for a connector"""
    try:
        manager = get_connector_manager()
        if not manager:
            raise HTTPException(status_code=500, detail="Connector manager not initialized")
        
        if provider_id not in manager.connectors:
            raise HTTPException(status_code=404, detail=f"Connector {provider_id} not found")
        
        connector = manager.connectors[provider_id]
        
        # Get user config
        config_key = f"user:{user_id}:connector:{provider_id}:config"
        config_data = await connector.redis_storage.redis_client.get(config_key, user_id)
        
        if config_data:
            config_dict = json.loads(config_data)
            enabled_tool_ids = set(config_dict.get("enabled_tools", []))
        else:
            enabled_tool_ids = set()
        
        # Get all available tools
        available_tools = connector.metadata.available_tools
        
        return {
            "provider_id": provider_id,
            "tools": [
                {
                    "id": tool.id,
                    "name": tool.name,
                    "description": tool.description,
                    "enabled": tool.id in enabled_tool_ids,
                    "requires_auth": tool.requires_auth
                }
                for tool in available_tools
            ]
        }
        
    except Exception as e:
        logger.error(
            "Failed to get connector tools",
            user_id=user_id,
            provider_id=provider_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{provider_id}/tools/update")
async def update_connector_tools(
    provider_id: str,
    request: UpdateToolsRequest,
    user_id: str = Depends(get_current_user_id)
):
    """Update enabled tools for a connector"""
    try:
        manager = get_connector_manager()
        if not manager:
            raise HTTPException(status_code=500, detail="Connector manager not initialized")
        
        success = await manager.update_user_tools(
            user_id,
            provider_id,
            request.enabled_tool_ids
        )
        
        return {
            "success": success,
            "provider_id": provider_id,
            "enabled_tools": list(request.enabled_tool_ids),
            "message": "Tools updated successfully"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            "Failed to update connector tools",
            user_id=user_id,
            provider_id=provider_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{provider_id}/enable")
async def enable_connector(
    provider_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Enable a connector for the user (must be authenticated first)"""
    try:
        manager = get_connector_manager()
        if not manager:
            raise HTTPException(status_code=500, detail="Connector manager not initialized")
        
        success = await manager.enable_user_connector(user_id, provider_id)
        
        return {
            "success": success,
            "provider_id": provider_id,
            "message": "Connector enabled successfully"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            "Failed to enable connector",
            user_id=user_id,
            provider_id=provider_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{provider_id}/disable")
async def disable_connector(
    provider_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Disable a connector for the user (keeps authentication)"""
    try:
        manager = get_connector_manager()
        if not manager:
            raise HTTPException(status_code=500, detail="Connector manager not initialized")

        success = await manager.disable_user_connector(user_id, provider_id)

        return {
            "success": success,
            "provider_id": provider_id,
            "message": "Connector disabled successfully"
        }

    except Exception as e:
        logger.error(
            "Failed to disable connector",
            user_id=user_id,
            provider_id=provider_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{provider_id}/toggle-chat")
async def toggle_connector_chat(
    provider_id: str,
    request: ToggleChatRequest,
    user_id: str = Depends(get_current_user_id)
):
    """Toggle whether a connector is available in chat context"""
    try:
        manager = get_connector_manager()
        if not manager:
            raise HTTPException(status_code=500, detail="Connector manager not initialized")

        if provider_id not in manager.connectors:
            raise HTTPException(status_code=404, detail=f"Connector {provider_id} not found")

        connector = manager.connectors[provider_id]

        # Get current user config
        config_key = f"user:{user_id}:connector:{provider_id}:config"
        config_data = await connector.redis_storage.redis_client.get(config_key, user_id)

        if config_data:
            config_dict = json.loads(config_data)
        else:
            config_dict = {}

        # Update enabled_in_chat setting
        config_dict["enabled_in_chat"] = request.enabled

        # Save updated config
        await connector.redis_storage.redis_client.set(
            config_key,
            json.dumps(config_dict),
            user_id
        )

        # Invalidate the tool cache so changes take effect immediately
        manager._invalidate_user_cache(user_id, provider_id)

        logger.info(
            "Toggled connector chat availability",
            user_id=user_id,
            provider_id=provider_id,
            enabled=request.enabled
        )

        return {
            "success": True,
            "provider_id": provider_id,
            "enabled_in_chat": request.enabled,
            "message": f"Connector {'enabled' if request.enabled else 'disabled'} in chat"
        }

    except Exception as e:
        logger.error(
            "Failed to toggle connector chat availability",
            user_id=user_id,
            provider_id=provider_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))