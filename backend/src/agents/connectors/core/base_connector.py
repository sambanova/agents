"""
Base OAuth Connector Framework with User-Level Management

Combines battle-tested components from:
- Authlib for OAuth flows
- Meltano Singer SDK patterns for token management
- User-level isolation for multi-tenant support
- Redis-based storage matching existing app patterns
"""

import json
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx
import structlog
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.oauth2.rfc7636 import create_s256_code_challenge
from authlib.common.security import generate_token
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class OAuthVersion(Enum):
    """Supported OAuth versions"""
    OAUTH1_0A = "1.0a"
    OAUTH2_0 = "2.0"


class ConnectorStatus(Enum):
    """User's connector connection status"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    EXPIRED = "expired"
    REFRESHING = "refreshing"
    NOT_CONFIGURED = "not_configured"


class GrantType(Enum):
    """OAuth 2.0 grant types"""
    AUTHORIZATION_CODE = "authorization_code"
    CLIENT_CREDENTIALS = "client_credentials"
    REFRESH_TOKEN = "refresh_token"
    DEVICE_CODE = "urn:ietf:params:oauth:grant-type:device_code"


@dataclass
class OAuthConfig:
    """System-level OAuth configuration for a provider"""
    provider_id: str  # e.g., "google", "slack", "atlassian"
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    redirect_uri: str
    scopes: List[str] = field(default_factory=list)
    oauth_version: OAuthVersion = OAuthVersion.OAUTH2_0
    use_pkce: bool = True
    grant_type: GrantType = GrantType.AUTHORIZATION_CODE
    additional_params: Dict[str, Any] = field(default_factory=dict)
    revoke_url: Optional[str] = None
    userinfo_url: Optional[str] = None
    
    def to_authlib_config(self) -> Dict[str, Any]:
        """Convert to Authlib client configuration"""
        return {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "authorize_url": self.authorize_url,
            "access_token_url": self.token_url,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scopes) if self.scopes else None,
            "grant_type": self.grant_type.value,
            **self.additional_params
        }


@dataclass
class UserOAuthToken:
    """User-specific OAuth token data"""
    user_id: str
    provider_id: str
    access_token: str  # Encrypted in storage
    token_type: str = "Bearer"
    refresh_token: Optional[str] = None  # Encrypted in storage
    expires_at: Optional[datetime] = None
    scope: Optional[str] = None
    id_token: Optional[str] = None  # Encrypted in storage
    additional_data: Dict[str, Any] = field(default_factory=dict)
    last_refreshed: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def is_expired(self) -> bool:
        """Check if the token is expired with buffer"""
        if self.expires_at is None:
            return False
        # Add 60 second buffer for network latency
        buffer = timedelta(seconds=60)
        return datetime.utcnow() >= (self.expires_at - buffer)
    
    @property
    def needs_refresh(self) -> bool:
        """Check if token should be refreshed (Singer SDK pattern)"""
        if not self.refresh_token:
            return False
        if self.is_expired:
            return True
        # Refresh if more than 80% of lifetime has passed
        if self.expires_at and self.last_refreshed:
            total_lifetime = (self.expires_at - self.last_refreshed).total_seconds()
            elapsed = (datetime.utcnow() - self.last_refreshed).total_seconds()
            return elapsed > (total_lifetime * 0.8)
        return False
    
    def to_redis_dict(self) -> Dict[str, Any]:
        """Serialize token for Redis storage (encryption handled by SecureRedisService)"""
        return {
            "user_id": self.user_id,
            "provider_id": self.provider_id,
            "access_token": self.access_token,
            "token_type": self.token_type,
            "refresh_token": self.refresh_token or "",  # Ensure not None
            "expires_at": self.expires_at.isoformat() if self.expires_at else "",
            "scope": self.scope or "",
            "id_token": self.id_token or "",
            "additional_data": json.dumps(self.additional_data) if self.additional_data else "{}",
            "last_refreshed": self.last_refreshed.isoformat() if self.last_refreshed else "",
            "created_at": self.created_at.isoformat() if self.created_at else ""
        }
    
    @classmethod
    def from_redis_dict(cls, data: Dict[str, Any]) -> "UserOAuthToken":
        """Deserialize token from Redis storage (decryption handled by SecureRedisService)"""
        # Helper function to convert bytes to string if needed
        def to_str(value: Any) -> Optional[str]:
            if value is None:
                return None
            if isinstance(value, bytes):
                return value.decode('utf-8')
            return str(value) if value else None
        
        # Helper function to parse datetime safely
        def parse_datetime(value: Any) -> Optional[datetime]:
            value_str = to_str(value)
            if value_str and value_str.strip():
                try:
                    return datetime.fromisoformat(value_str)
                except (ValueError, TypeError):
                    return None
            return None
        
        # Convert all bytes to strings first
        clean_data = {}
        for key, value in data.items():
            if isinstance(value, bytes):
                clean_data[key] = value.decode('utf-8')
            else:
                clean_data[key] = value
        
        return cls(
            user_id=to_str(clean_data["user_id"]),
            provider_id=to_str(clean_data["provider_id"]),
            access_token=to_str(clean_data["access_token"]),
            token_type=to_str(clean_data.get("token_type")) or "Bearer",
            refresh_token=to_str(clean_data.get("refresh_token")) or None,
            expires_at=parse_datetime(clean_data.get("expires_at")),
            scope=to_str(clean_data.get("scope")) or None,
            id_token=to_str(clean_data.get("id_token")) or None,
            additional_data=json.loads(clean_data.get("additional_data", "{}")) if clean_data.get("additional_data") else {},
            last_refreshed=parse_datetime(clean_data.get("last_refreshed")),
            created_at=parse_datetime(clean_data.get("created_at")) or datetime.utcnow()
        )


class UserConnectorConfig(BaseModel):
    """User-specific connector configuration"""
    user_id: str
    provider_id: str
    enabled: bool = False
    enabled_tools: Set[str] = Field(default_factory=set)  # Tool IDs the user has enabled
    custom_settings: Dict[str, Any] = Field(default_factory=dict)
    connected_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    status: ConnectorStatus = ConnectorStatus.NOT_CONFIGURED
    
    class Config:
        arbitrary_types_allowed = True
        use_enum_values = True
    
    def redis_key(self) -> str:
        """Generate Redis key for this user connector config"""
        return f"user:{self.user_id}:connector:{self.provider_id}:config"


class ConnectorTool(BaseModel):
    """Represents a tool provided by a connector"""
    id: str
    name: str
    description: str
    parameters_schema: Dict[str, Any] = Field(default_factory=dict)
    requires_auth: bool = True
    rate_limit: Optional[Dict[str, Any]] = None
    
    class Config:
        arbitrary_types_allowed = True


class ConnectorMetadata(BaseModel):
    """System-level metadata about a connector"""
    provider_id: str
    name: str
    description: str
    icon_url: Optional[str] = None
    oauth_version: OAuthVersion
    available_tools: List[ConnectorTool] = Field(default_factory=list)
    required_scopes: List[str] = Field(default_factory=list)
    optional_scopes: List[str] = Field(default_factory=list)
    rate_limits: Optional[Dict[str, Any]] = None
    
    class Config:
        arbitrary_types_allowed = True
        use_enum_values = True


class BaseOAuthConnector(ABC):
    """
    Base class for OAuth connectors with user-level management
    """
    
    def __init__(self, config: OAuthConfig, redis_storage):
        self.config = config
        self.redis_storage = redis_storage  # RedisStorage instance from your app
        self.metadata = self._get_metadata()
        self._oauth_clients: Dict[str, AsyncOAuth2Client] = {}  # Cache per user
        self._state_store: Dict[str, Dict[str, Any]] = {}  # Temporary state storage
    
    @abstractmethod
    def _get_metadata(self) -> ConnectorMetadata:
        """Get connector metadata"""
        pass
    
    async def get_oauth_client(self, user_id: str) -> AsyncOAuth2Client:
        """Get or create Authlib OAuth client for a user"""
        cache_key = f"{user_id}:{self.config.provider_id}"
        if cache_key not in self._oauth_clients:
            config = self.config.to_authlib_config()
            self._oauth_clients[cache_key] = AsyncOAuth2Client(**config)
        return self._oauth_clients[cache_key]
    
    async def get_user_connector_status(self, user_id: str) -> ConnectorStatus:
        """Get the connection status for a specific user"""
        # Check if user has token stored
        token_key = f"user:{user_id}:connector:{self.config.provider_id}:token"
        token_data = await self.redis_storage.redis_client.hgetall(token_key, user_id)
        
        if not token_data:
            return ConnectorStatus.NOT_CONFIGURED
        
        # Check token validity
        try:
            token = UserOAuthToken.from_redis_dict(token_data)
            if token.is_expired:
                if token.refresh_token:
                    # We have a refresh token, so we can auto-refresh - treat as connected
                    return ConnectorStatus.CONNECTED
                else:
                    return ConnectorStatus.ERROR
            return ConnectorStatus.CONNECTED
        except Exception as e:
            logger.error(
                "Error checking connector status",
                user_id=user_id,
                provider=self.config.provider_id,
                error=str(e),
                exc_info=True
            )
            # If we have a token with access_token, consider it connected despite parsing errors
            if token_data and token_data.get("access_token"):
                logger.info("Token has access_token, considering as connected despite parsing error")
                return ConnectorStatus.CONNECTED
            return ConnectorStatus.ERROR
    
    async def get_user_enabled_tools(self, user_id: str) -> List[ConnectorTool]:
        """Get tools enabled by a specific user for this connector"""
        config_key = f"user:{user_id}:connector:{self.config.provider_id}:config"
        config_data = await self.redis_storage.redis_client.get(config_key, user_id)
        
        if not config_data:
            return []
        
        user_config = UserConnectorConfig(**json.loads(config_data))
        if not user_config.enabled:
            return []
        
        return [
            tool for tool in self.metadata.available_tools
            if tool.id in user_config.enabled_tools
        ]
    
    async def set_user_enabled_tools(self, user_id: str, tool_ids: Set[str]) -> None:
        """Set which tools a user has enabled for this connector"""
        config_key = f"user:{user_id}:connector:{self.config.provider_id}:config"
        config_data = await self.redis_storage.redis_client.get(config_key, user_id)
        
        if config_data:
            config_dict = json.loads(config_data)
        else:
            config_dict = {}
        
        # Remove user_id and provider_id from config_dict to avoid duplicate keyword arguments
        config_dict.pop('user_id', None)
        config_dict.pop('provider_id', None)
        
        user_config = UserConnectorConfig(
            user_id=user_id,
            provider_id=self.config.provider_id,
            **config_dict
        )
        user_config.enabled_tools = tool_ids
        user_config.last_used = datetime.utcnow()
        
        # Serialize with JSON serializable conversion
        config_data = user_config.model_dump(mode='json')
        config_json = json.dumps(config_data)
        
        await self.redis_storage.redis_client.set(
            config_key, 
            config_json, 
            user_id
        )
    
    async def get_authorization_url(self, user_id: str, state: Optional[str] = None, **kwargs) -> Tuple[str, str]:
        """
        Generate authorization URL for a specific user with PKCE support
        
        Returns:
            Tuple of (authorization_url, state)
        """
        client = await self.get_oauth_client(user_id)
        
        # Generate state if not provided
        if state is None:
            state = secrets.token_urlsafe(32)
        
        # Setup PKCE if enabled
        code_verifier = None
        code_challenge = None
        if self.config.use_pkce:
            code_verifier = generate_token(48)  # 48 bytes for code verifier
            code_challenge = create_s256_code_challenge(code_verifier)
        
        # Store state data with user context
        self._state_store[state] = {
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "code_verifier": code_verifier,
            "provider_id": self.config.provider_id,
            **kwargs
        }
        
        # Store state in Redis for persistence across requests
        # Use plain Redis for OAuth state (no encryption needed, temporary data)
        state_key = f"oauth:state:{state}"
        state_value = json.dumps(self._state_store[state])
        
        logger.info(
            "Storing OAuth state",
            state_key=state_key,
            state=state[:10] + "..." if state else None,
            user_id=user_id
        )
        
        from redis.asyncio import Redis
        plain_redis = Redis(connection_pool=self.redis_storage.redis_client.connection_pool, decode_responses=True)
        await plain_redis.setex(
            state_key, 
            600,  # 10 minute TTL
            state_value
        )
        await plain_redis.close()
        
        logger.info("OAuth state stored successfully", state_key=state_key)
        
        # DEBUG: Log OAuth configuration details
        logger.info(
            "DEBUG: OAuth configuration for authorization",
            provider=self.config.provider_id,
            authorize_url=self.config.authorize_url,
            redirect_uri=self.config.redirect_uri,
            client_id=self.config.client_id[:20] + "..." if self.config.client_id else None,
            scopes=self.config.scopes,
            use_pkce=self.config.use_pkce
        )
        
        # Build authorization URL
        auth_url, _ = client.create_authorization_url(
            self.config.authorize_url,
            state=state,
            code_challenge=code_challenge,
            code_challenge_method="S256" if code_challenge else None,
            **kwargs
        )
        
        # DEBUG: Log the complete authorization URL
        logger.info(
            "DEBUG: Full authorization URL generated",
            full_url=auth_url,
            provider=self.config.provider_id
        )
        
        logger.info(
            "Generated authorization URL",
            user_id=user_id,
            connector=self.config.provider_id,
            state=state[:8] + "..."
        )
        
        return auth_url, state
    
    async def exchange_code_for_token(self, code: str, state: str, user_id: str) -> UserOAuthToken:
        """
        Exchange authorization code for access token for a specific user
        """
        # Retrieve state from Redis using plain Redis
        state_key = f"oauth:state:{state}"
        from redis.asyncio import Redis
        plain_redis = Redis(connection_pool=self.redis_storage.redis_client.connection_pool, decode_responses=True)
        state_json = await plain_redis.get(state_key)
        
        if not state_json:
            await plain_redis.close()
            logger.error("OAuth state not found during token exchange", state_key=state_key)
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
        
        code_verifier = state_data.get("code_verifier")
        
        # Delete state from Redis
        await plain_redis.delete(state_key)
        await plain_redis.close()
        
        logger.info("OAuth state validated and deleted", state_key=state_key)
        
        client = await self.get_oauth_client(user_id)
        
        # Exchange code for token
        token_data = await client.fetch_token(
            self.config.token_url,
            code=code,
            code_verifier=code_verifier,
            client_id=self.config.client_id,
            client_secret=self.config.client_secret
        )
        
        # Create user token
        token = self._parse_token_response(token_data, user_id)
        
        # Store token in Redis
        await self.store_user_token(token)
        
        # Update user connector config
        await self._update_user_connector_status(user_id, ConnectorStatus.CONNECTED)
        
        logger.info(
            "Successfully exchanged code for token",
            user_id=user_id,
            connector=self.config.provider_id,
            has_refresh_token=bool(token.refresh_token)
        )
        
        return token
    
    async def refresh_user_token(self, user_id: str) -> UserOAuthToken:
        """
        Refresh token for a specific user
        """
        # Get existing token WITHOUT auto-refresh to avoid recursion
        token = await self.get_user_token(user_id, auto_refresh=False)
        if not token or not token.refresh_token:
            raise ValueError("No refresh token available")
        
        client = await self.get_oauth_client(user_id)
        
        token_data = await client.fetch_token(
            self.config.token_url,
            grant_type="refresh_token",
            refresh_token=token.refresh_token,
            client_id=self.config.client_id,
            client_secret=self.config.client_secret
        )
        
        # Create new token
        new_token = self._parse_token_response(token_data, user_id)
        new_token.refresh_token = new_token.refresh_token or token.refresh_token  # Keep old refresh token if not provided
        new_token.last_refreshed = datetime.utcnow()
        
        # Store updated token
        await self.store_user_token(new_token)
        
        logger.info(
            "Successfully refreshed token",
            user_id=user_id,
            connector=self.config.provider_id
        )
        
        return new_token
    
    async def store_user_token(self, token: UserOAuthToken) -> None:
        """Store user token in Redis (encryption handled automatically)"""
        # Ensure user_id and provider_id are strings, not bytes
        user_id = token.user_id.decode() if isinstance(token.user_id, bytes) else token.user_id
        provider_id = token.provider_id.decode() if isinstance(token.provider_id, bytes) else token.provider_id
        
        token_key = f"user:{user_id}:connector:{provider_id}:token"
        token_data = token.to_redis_dict()
        
        logger.info(
            "Storing user token",
            token_key=token_key,
            user_id=user_id,
            has_refresh_token=bool(token.refresh_token),
            token_fields=list(token_data.keys())
        )
        
        # SecureRedisService.hset expects (name, mapping, user_id)
        await self.redis_storage.redis_client.hset(
            token_key,
            token_data,
            user_id
        )
        
        logger.info("Token stored successfully", token_key=token_key)
    
    async def get_user_token(self, user_id: str, auto_refresh: bool = True) -> Optional[UserOAuthToken]:
        """
        Retrieve user token from Redis with optional automatic refresh
        
        Args:
            user_id: User ID
            auto_refresh: Whether to automatically refresh expired tokens
            
        Returns:
            Valid token or None
        """
        token_key = f"user:{user_id}:connector:{self.config.provider_id}:token"
        token_data = await self.redis_storage.redis_client.hgetall(token_key, user_id)
        
        if not token_data:
            return None
        
        token = UserOAuthToken.from_redis_dict(token_data)
        
        # Check if token needs refresh and auto_refresh is enabled
        if auto_refresh and token.needs_refresh and token.refresh_token:
            try:
                logger.info(
                    "Auto-refreshing expired token",
                    user_id=user_id,
                    provider=self.config.provider_id
                )
                token = await self.refresh_user_token(user_id)
            except Exception as e:
                logger.error(
                    "Failed to auto-refresh token",
                    user_id=user_id,
                    provider=self.config.provider_id,
                    error=str(e)
                )
                # Return original token if still valid
                if not token.is_expired:
                    return token
                return None
        
        return token
    
    async def revoke_user_token(self, user_id: str) -> bool:
        """
        Revoke token for a specific user
        """
        token = await self.get_user_token(user_id)
        if not token:
            return False
        
        # Revoke with provider if supported
        if self.config.revoke_url:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        self.config.revoke_url,
                        data={
                            "token": token.access_token,
                            "token_type_hint": "access_token",
                            "client_id": self.config.client_id,
                            "client_secret": self.config.client_secret
                        }
                    )
                    response.raise_for_status()
            except Exception as e:
                logger.error(
                    "Failed to revoke token with provider",
                    user_id=user_id,
                    provider=self.config.provider_id,
                    error=str(e)
                )
        
        # Delete from Redis
        token_key = f"user:{user_id}:connector:{self.config.provider_id}:token"
        await self.redis_storage.redis_client.delete(token_key)
        
        # Update connector status
        await self._update_user_connector_status(user_id, ConnectorStatus.DISCONNECTED)
        
        logger.info(
            "Revoked user token",
            user_id=user_id,
            connector=self.config.provider_id
        )
        
        return True
    
    @abstractmethod
    async def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """
        Get user information using their stored access token
        """
        pass
    
    def _parse_token_response(self, token_data: Dict[str, Any], user_id: str) -> UserOAuthToken:
        """
        Parse token response into UserOAuthToken object
        """
        expires_in = token_data.get("expires_in")
        expires_at = None
        if expires_in:
            expires_at = datetime.utcnow() + timedelta(seconds=int(expires_in))
        
        return UserOAuthToken(
            user_id=user_id,
            provider_id=self.config.provider_id,
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            refresh_token=token_data.get("refresh_token"),
            expires_at=expires_at,
            scope=token_data.get("scope"),
            id_token=token_data.get("id_token"),
            additional_data={
                k: v for k, v in token_data.items() 
                if k not in ["access_token", "token_type", "refresh_token", "expires_in", "scope", "id_token"]
            },
            last_refreshed=datetime.utcnow()
        )
    
    async def _update_user_connector_status(self, user_id: str, status: ConnectorStatus) -> None:
        """Update user's connector status"""
        config_key = f"user:{user_id}:connector:{self.config.provider_id}:config"
        config_data = await self.redis_storage.redis_client.get(config_key, user_id)
        
        if config_data:
            config_dict = json.loads(config_data)
        else:
            config_dict = {}
        
        # Remove user_id and provider_id from config_dict to avoid duplicate keyword arguments
        config_dict.pop('user_id', None)
        config_dict.pop('provider_id', None)
        
        user_config = UserConnectorConfig(
            user_id=user_id,
            provider_id=self.config.provider_id,
            **config_dict
        )
        user_config.status = status
        if status == ConnectorStatus.CONNECTED and not user_config.connected_at:
            user_config.connected_at = datetime.utcnow()
            user_config.enabled = True
        
        # Serialize with JSON serializable conversion
        config_data = user_config.model_dump(mode='json')
        config_json = json.dumps(config_data)
        
        await self.redis_storage.redis_client.set(
            config_key, 
            config_json, 
            user_id
        )