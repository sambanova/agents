"""
PayPal MCP Connector with OAuth 2.0 Authentication

This connector integrates with PayPal's MCP server for payment processing,
invoice management, and financial services.

Uses OAuth 2.0 Authorization Code flow to support multiple users, where each
user can connect and authorize access to their own PayPal account.
"""

import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

import structlog
from langchain.tools import BaseTool

from agents.connectors.core.mcp_connector import MCPConnector, MCPConfig
from agents.connectors.core.base_connector import (
    ConnectorMetadata,
    ConnectorTool,
    OAuthConfig,
    OAuthVersion,
    UserOAuthToken
)

logger = structlog.get_logger(__name__)


class PayPalConnector(MCPConnector):
    """
    PayPal connector using MCP protocol with OAuth 2.0.
    
    This connector provides access to PayPal's payment processing, invoice management,
    and financial services through their MCP server.
    """
    
    def __init__(self, redis_storage):
        """
        Initialize PayPal connector with OAuth and MCP configuration.
        
        For sandbox/development:
        - OAuth: https://api-m.sandbox.paypal.com
        - MCP: https://mcp.sandbox.paypal.com
        
        For production:
        - OAuth: https://api-m.paypal.com
        - MCP: https://mcp.paypal.com
        """
        # Use sandbox for development/testing
        # For multi-user OAuth testing, we'll use sandbox environment
        use_sandbox = True  # Always use sandbox for now
        
        if use_sandbox:
            # Different URLs for different parts of OAuth flow
            oauth_authorize_url = "https://www.sandbox.paypal.com/connect"  # User authorization
            oauth_token_url = "https://api-m.sandbox.paypal.com/v1/oauth2/token"  # Token exchange
            mcp_url = "https://mcp.sandbox.paypal.com/sse"  # MCP server SSE endpoint
        else:
            oauth_authorize_url = "https://www.paypal.com/connect"  # User authorization
            oauth_token_url = "https://api-m.paypal.com/v1/oauth2/token"  # Token exchange
            mcp_url = "https://mcp.paypal.com/sse"  # MCP server SSE endpoint
        
        # OAuth configuration for PayPal
        # Uses "Connect with PayPal" for multi-user authorization
        oauth_config = OAuthConfig(
            provider_id="paypal",
            client_id="",  # Will be set from environment
            client_secret="",  # Will be set from environment
            authorize_url=oauth_authorize_url,  # Connect with PayPal endpoint
            token_url=oauth_token_url,  # Token exchange endpoint
            redirect_uri="",  # Will be set from environment
            scopes=[],  # PayPal doesn't require explicit scopes - they're auto-assigned
            oauth_version=OAuthVersion.OAUTH2_0
        )
        
        # MCP configuration for PayPal
        mcp_config = MCPConfig(
            provider_id="paypal",
            client_id=oauth_config.client_id,
            client_secret=oauth_config.client_secret,
            authorize_url=oauth_config.authorize_url,
            token_url=oauth_config.token_url,
            redirect_uri=oauth_config.redirect_uri,
            scopes=oauth_config.scopes,
            oauth_version=OAuthVersion.OAUTH2_0,
            mcp_server_url=mcp_url,
            transport_type="sse"  # PayPal MCP supports SSE
        )
        
        # Initialize parent class with MCP config
        super().__init__(mcp_config, redis_storage)
        
        # Store OAuth config for reference
        self.oauth_config = oauth_config
        self.is_sandbox = use_sandbox
    
    def _get_mcp_server_info(self) -> Dict[str, Any]:
        """Get PayPal MCP server information"""
        return {
            "server_url": self.mcp_config.mcp_server_url,
            "server_type": "paypal-official",
            "environment": "sandbox" if self.is_sandbox else "production",
            "transport": self.mcp_config.transport_type,
            "oauth_enabled": True,
            "supported_features": ["payments", "invoicing", "disputes"]
        }
    
    def _get_metadata(self) -> ConnectorMetadata:
        """
        Get PayPal connector metadata.
        
        Returns metadata about the PayPal connector including available tools
        and required OAuth scopes.
        """
        return ConnectorMetadata(
            provider_id="paypal",
            name="PayPal",
            description="Access PayPal payment processing, invoicing, and financial services",
            icon_url="https://www.paypalobjects.com/webstatic/icon/pp258.png",
            oauth_version=OAuthVersion.OAUTH2_0,
            available_tools=[
                # Product Management
                ConnectorTool(
                    id="create_product",
                    name="Create Product",
                    description="Create a new product in PayPal catalog"
                ),
                ConnectorTool(
                    id="list_product",
                    name="List Products",
                    description="List products from PayPal catalog"
                ),
                ConnectorTool(
                    id="show_product_details",
                    name="Show Product Details",
                    description="Get details of a specific product"
                ),
                
                # Invoice Management
                ConnectorTool(
                    id="create_invoice",
                    name="Create Invoice",
                    description="Create a new invoice"
                ),
                ConnectorTool(
                    id="list_invoices",
                    name="List Invoices",
                    description="List all invoices"
                ),
                ConnectorTool(
                    id="get_invoice",
                    name="Get Invoice",
                    description="Get details of a specific invoice"
                ),
                ConnectorTool(
                    id="send_invoice",
                    name="Send Invoice",
                    description="Send an invoice to customer"
                ),
                ConnectorTool(
                    id="send_invoice_reminder",
                    name="Send Invoice Reminder",
                    description="Send a reminder for an invoice"
                ),
                ConnectorTool(
                    id="cancel_sent_invoice",
                    name="Cancel Sent Invoice",
                    description="Cancel an invoice that was sent"
                ),
                
                # Dispute Management
                ConnectorTool(
                    id="list_disputes",
                    name="List Disputes",
                    description="List all disputes"
                ),
                ConnectorTool(
                    id="get_dispute",
                    name="Get Dispute",
                    description="Get details of a specific dispute"
                ),
                ConnectorTool(
                    id="accept_dispute_claim",
                    name="Accept Dispute Claim",
                    description="Accept a dispute claim"
                ),
            ],
            required_scopes=[
                # For "Log in with PayPal" (Connect with PayPal), only OpenID Connect scopes work
                # API access (invoicing, disputes) is granted via app permissions, not OAuth scopes
                "openid",  # Required for OpenID Connect
                "profile",  # For user's full name  
                "email",  # For user's email
                "address",  # For user's address (you have this enabled in PayPal)
            ],
            optional_scopes=[
                # These are additional OpenID Connect scopes
                "phone",  # Phone number (if you enable it in the UI)
            ]
        )
    
    async def initialize(self, 
                        client_id: str, 
                        client_secret: str,
                        redirect_uri: str,
                        scopes: Optional[List[str]] = None) -> None:
        """
        Initialize the PayPal connector with credentials.
        
        Args:
            client_id: PayPal OAuth client ID
            client_secret: PayPal OAuth client secret
            redirect_uri: OAuth redirect URI
            scopes: Optional list of OAuth scopes (uses defaults if not provided)
        """
        # Use provided scopes or default to required scopes
        if scopes is None:
            scopes = self.metadata.required_scopes
        
        # Update OAuth configuration
        self.oauth_config.client_id = client_id
        self.oauth_config.client_secret = client_secret
        self.oauth_config.redirect_uri = redirect_uri
        self.oauth_config.scopes = scopes if scopes else []
        
        # Update MCP configuration
        self.mcp_config.client_id = client_id
        self.mcp_config.client_secret = client_secret
        self.mcp_config.redirect_uri = redirect_uri
        self.mcp_config.scopes = self.oauth_config.scopes
        
        logger.info(
            "PayPal connector initialized",
            is_sandbox=self.is_sandbox,
            redirect_uri=redirect_uri,
            scopes=scopes
        )
    
    async def exchange_code_for_token(
        self,
        code: str,
        state: str,
        user_id: str
    ) -> UserOAuthToken:
        """
        Exchange authorization code for access token.
        
        PayPal uses standard OAuth 2.0 flow without PKCE.
        """
        # Get state from Redis to validate
        from redis.asyncio import Redis
        plain_redis = Redis(
            connection_pool=self.redis_storage.redis_client.connection_pool,
            decode_responses=True
        )
        
        state_key = f"oauth:state:{state}"
        state_json = await plain_redis.get(state_key)
        
        if not state_json:
            await plain_redis.close()
            logger.error("OAuth state not found", state_key=state_key)
            raise ValueError("Invalid or expired state parameter")
        
        state_data = json.loads(state_json)
        
        # Validate user matches
        if state_data.get("user_id") != user_id:
            await plain_redis.close()
            logger.error(
                "State user mismatch",
                state_user_id=state_data.get("user_id"),
                provided_user_id=user_id
            )
            raise ValueError("State does not match user")
        
        # Get PKCE code_verifier from state data
        code_verifier = state_data.get("code_verifier")
        
        # Delete state from Redis
        await plain_redis.delete(state_key)
        await plain_redis.close()
        
        # Exchange code for token with PayPal
        import httpx
        
        token_params = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.mcp_config.redirect_uri
        }
        
        # Add PKCE code_verifier if present (required for PayPal)
        if code_verifier:
            token_params["code_verifier"] = code_verifier
        
        logger.info(
            "Exchanging code for PayPal token",
            user_id=user_id,
            redirect_uri=self.mcp_config.redirect_uri,
            is_sandbox=self.is_sandbox,
            has_code_verifier=bool(code_verifier)
        )
        
        async with httpx.AsyncClient() as client:
            # PayPal uses Basic Auth for client credentials
            response = await client.post(
                self.mcp_config.token_url,
                data=token_params,
                auth=(self.mcp_config.client_id, self.mcp_config.client_secret),
                headers={
                    "Accept": "application/json",
                    "Accept-Language": "en_US"
                }
            )
            
            if response.status_code != 200:
                logger.error(
                    "PayPal token exchange failed",
                    status_code=response.status_code,
                    response=response.text
                )
                raise ValueError(f"Token exchange failed: {response.text}")
            
            token_data = response.json()
        
        # Parse the token response
        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=int(expires_in))
        
        # PayPal may not always return refresh tokens
        refresh_token = token_data.get("refresh_token")
        if not refresh_token:
            logger.warning(
                "No refresh token received from PayPal",
                user_id=user_id,
                scope=token_data.get("scope")
            )
        
        token = UserOAuthToken(
            user_id=user_id,
            provider_id=self.mcp_config.provider_id,
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            refresh_token=refresh_token,
            expires_at=expires_at,
            scope=token_data.get("scope"),
            additional_data={
                "app_id": token_data.get("app_id"),
                "nonce": token_data.get("nonce"),
                "token_issued_at": datetime.utcnow().isoformat()
            },
            last_refreshed=datetime.utcnow()
        )
        
        # Store token
        await self.store_user_token(token)
        
        # Update connector status
        from agents.connectors.core.base_connector import ConnectorStatus
        await self._update_user_connector_status(user_id, ConnectorStatus.CONNECTED)
        
        logger.info(
            "Successfully exchanged code for PayPal token",
            user_id=user_id,
            has_refresh_token=bool(token.refresh_token),
            scope=token.scope
        )
        
        return token
    
    async def refresh_user_token(self, user_id: str) -> UserOAuthToken:
        """
        Refresh PayPal access token.
        
        PayPal supports refresh tokens but may not always provide them.
        """
        # Get existing token WITHOUT auto-refresh to avoid recursion
        token = await self.get_user_token(user_id, auto_refresh=False)
        if not token or not token.refresh_token:
            raise ValueError("No refresh token available")
        
        import httpx
        
        logger.info(
            "Refreshing PayPal token",
            user_id=user_id,
            has_refresh_token=bool(token.refresh_token)
        )
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.mcp_config.token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": token.refresh_token
                },
                auth=(self.mcp_config.client_id, self.mcp_config.client_secret),
                headers={
                    "Accept": "application/json",
                    "Accept-Language": "en_US"
                }
            )
            
            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get("error_description", response.text)
                logger.error(
                    "PayPal token refresh failed",
                    user_id=user_id,
                    status_code=response.status_code,
                    error=error_msg
                )
                raise ValueError(f"Token refresh failed: {error_msg}")
            
            token_data = response.json()
        
        # Parse refreshed token
        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=int(expires_in))
        
        # Create new token with refreshed data
        new_token = UserOAuthToken(
            user_id=user_id,
            provider_id=self.mcp_config.provider_id,
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            refresh_token=token_data.get("refresh_token") or token.refresh_token,  # Keep old refresh token if new one not provided
            expires_at=expires_at,
            scope=token_data.get("scope", token.scope),
            additional_data={
                "app_id": token_data.get("app_id"),
                "refreshed_at": datetime.utcnow().isoformat()
            },
            last_refreshed=datetime.utcnow()
        )
        
        # Store updated token
        await self.store_user_token(new_token)
        
        logger.info(
            "Successfully refreshed PayPal token",
            user_id=user_id,
            new_expiry=expires_at.isoformat()
        )
        
        return new_token
    
    async def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """
        Get PayPal user information.
        
        Uses PayPal's identity API to get user profile information.
        """
        token = await self.get_user_token(user_id, auto_refresh=True)
        if not token:
            raise ValueError("No token found for user")
        
        import httpx
        
        # Determine the correct API endpoint
        if self.is_sandbox:
            api_base = "https://api-m.sandbox.paypal.com"
        else:
            api_base = "https://api-m.paypal.com"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{api_base}/v1/identity/openidconnect/userinfo",
                headers={
                    "Authorization": f"Bearer {token.access_token}",
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code == 200:
                user_data = response.json()
                return {
                    "user_id": user_data.get("user_id"),
                    "email": user_data.get("email"),
                    "name": user_data.get("name"),
                    "verified_account": user_data.get("verified_account"),
                    "payer_id": user_data.get("payer_id"),
                    "raw": user_data
                }
            else:
                logger.error(
                    "Failed to get PayPal user info",
                    status_code=response.status_code,
                    response=response.text[:500] if response.text else None
                )
                return {
                    "error": f"Failed to get user info: {response.status_code}"
                }