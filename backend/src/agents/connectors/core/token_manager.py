"""
Token Manager for OAuth Connectors

Provides composable token refresh functionality for all OAuth connectors.
Handles automatic token refresh, token validation, and secure storage.
"""

import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Protocol

import structlog
from agents.connectors.core.base_connector import UserOAuthToken
from agents.storage.redis_storage import RedisStorage

logger = structlog.get_logger(__name__)


class TokenRefreshStrategy(ABC):
    """Abstract base class for token refresh strategies"""
    
    @abstractmethod
    async def refresh_token(
        self,
        token: UserOAuthToken,
        config: Dict[str, Any]
    ) -> UserOAuthToken:
        """
        Refresh the token using provider-specific logic
        
        Args:
            token: Current token to refresh
            config: Provider-specific configuration (client_id, client_secret, etc.)
            
        Returns:
            Refreshed token
        """
        pass
    
    @abstractmethod
    def can_refresh(self, token: UserOAuthToken) -> bool:
        """
        Check if token can be refreshed
        
        Args:
            token: Token to check
            
        Returns:
            True if token can be refreshed
        """
        pass


class OAuth2RefreshStrategy(TokenRefreshStrategy):
    """Standard OAuth 2.0 refresh token strategy"""
    
    def __init__(self, token_url: str):
        self.token_url = token_url
    
    async def refresh_token(
        self,
        token: UserOAuthToken,
        config: Dict[str, Any]
    ) -> UserOAuthToken:
        """Refresh OAuth 2.0 token"""
        if not token.refresh_token:
            raise ValueError("No refresh token available")
        
        import httpx
        from authlib.integrations.httpx_client import AsyncOAuth2Client
        
        client = AsyncOAuth2Client(
            client_id=config['client_id'],
            client_secret=config['client_secret'],
            token=token.model_dump()
        )
        
        try:
            new_token_data = await client.refresh_token(
                self.token_url,
                refresh_token=token.refresh_token
            )
            
            # Create new token object with refreshed data
            new_token = UserOAuthToken(
                user_id=token.user_id,
                provider_id=token.provider_id,
                access_token=new_token_data['access_token'],
                refresh_token=new_token_data.get('refresh_token', token.refresh_token),
                token_type=new_token_data.get('token_type', 'Bearer'),
                expires_at=datetime.fromtimestamp(
                    new_token_data.get('expires_at', time.time() + 3600),
                    tz=timezone.utc
                ),
                scope=new_token_data.get('scope', token.scope),
                created_at=token.created_at,
                updated_at=datetime.now(timezone.utc)
            )
            
            logger.info(
                "Token refreshed successfully",
                user_id=token.user_id,
                provider_id=token.provider_id
            )
            
            return new_token
            
        except Exception as e:
            logger.error(
                "Failed to refresh OAuth2 token",
                user_id=token.user_id,
                provider_id=token.provider_id,
                error=str(e)
            )
            raise
    
    def can_refresh(self, token: UserOAuthToken) -> bool:
        """Check if OAuth2 token can be refreshed"""
        return bool(token.refresh_token)


class GoogleRefreshStrategy(OAuth2RefreshStrategy):
    """Google-specific OAuth 2.0 refresh strategy"""
    
    def __init__(self):
        super().__init__("https://oauth2.googleapis.com/token")
    
    async def refresh_token(
        self,
        token: UserOAuthToken,
        config: Dict[str, Any]
    ) -> UserOAuthToken:
        """
        Refresh Google OAuth token using google-auth library
        
        This provides better integration with Google APIs
        """
        if not token.refresh_token:
            raise ValueError("No refresh token available")
        
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            
            # Create credentials with all required fields
            creds = Credentials(
                token=token.access_token,
                refresh_token=token.refresh_token,
                token_uri=self.token_url,
                client_id=config['client_id'],
                client_secret=config['client_secret'],
                scopes=token.scope.split() if token.scope else []
            )
            
            # Refresh the token
            creds.refresh(Request())
            
            # Create new token object with refreshed data
            new_token = UserOAuthToken(
                user_id=token.user_id,
                provider_id=token.provider_id,
                access_token=creds.token,
                refresh_token=creds.refresh_token or token.refresh_token,
                token_type='Bearer',
                expires_at=creds.expiry.replace(tzinfo=timezone.utc) if creds.expiry else datetime.now(timezone.utc) + timedelta(hours=1),
                scope=token.scope,
                created_at=token.created_at,
                updated_at=datetime.now(timezone.utc)
            )
            
            logger.info(
                "Google token refreshed successfully",
                user_id=token.user_id,
                provider_id=token.provider_id
            )
            
            return new_token
            
        except ImportError:
            # Fallback to standard OAuth2 refresh if google-auth not available
            logger.warning("google-auth not available, using standard OAuth2 refresh")
            return await super().refresh_token(token, config)
        except Exception as e:
            logger.error(
                "Failed to refresh Google token",
                user_id=token.user_id,
                provider_id=token.provider_id,
                error=str(e)
            )
            raise


class TokenManager:
    """
    Manages token lifecycle for OAuth connectors
    
    Provides automatic refresh, validation, and storage
    """
    
    def __init__(
        self,
        redis_storage: RedisStorage,
        refresh_strategy: TokenRefreshStrategy,
        config: Dict[str, Any]
    ):
        self.redis_storage = redis_storage
        self.refresh_strategy = refresh_strategy
        self.config = config
        self.refresh_buffer = timedelta(minutes=5)  # Refresh 5 minutes before expiry
    
    async def get_valid_token(
        self,
        user_id: str,
        provider_id: str,
        force_refresh: bool = False
    ) -> Optional[UserOAuthToken]:
        """
        Get a valid token, refreshing if necessary
        
        Args:
            user_id: User ID
            provider_id: Provider ID
            force_refresh: Force token refresh even if not expired
            
        Returns:
            Valid token or None if not available
        """
        # Get current token
        token_key = f"user:{user_id}:connector:{provider_id}:token"
        token_data = await self.redis_storage.get_encrypted_dict(token_key, user_id)
        
        if not token_data:
            logger.warning(
                "No token found",
                user_id=user_id,
                provider_id=provider_id
            )
            return None
        
        token = UserOAuthToken(**token_data)
        
        # Check if refresh is needed
        if force_refresh or self._should_refresh(token):
            if self.refresh_strategy.can_refresh(token):
                try:
                    token = await self._refresh_and_store(token)
                except Exception as e:
                    logger.error(
                        "Token refresh failed",
                        user_id=user_id,
                        provider_id=provider_id,
                        error=str(e)
                    )
                    # Return existing token if refresh fails but token is still valid
                    if not token.is_expired:
                        return token
                    raise
            elif token.is_expired:
                logger.error(
                    "Token expired and cannot be refreshed",
                    user_id=user_id,
                    provider_id=provider_id
                )
                return None
        
        return token
    
    async def store_token(self, token: UserOAuthToken) -> None:
        """Store token in Redis"""
        token_key = f"user:{token.user_id}:connector:{token.provider_id}:token"
        await self.redis_storage.set_encrypted_dict(
            token_key,
            token.model_dump(mode='json'),
            token.user_id
        )
        
        logger.info(
            "Token stored",
            user_id=token.user_id,
            provider_id=token.provider_id
        )
    
    def _should_refresh(self, token: UserOAuthToken) -> bool:
        """Check if token should be refreshed"""
        if not token.expires_at:
            return False
        
        # Refresh if expired or within buffer period
        now = datetime.now(timezone.utc)
        expiry_with_buffer = token.expires_at - self.refresh_buffer
        
        return now >= expiry_with_buffer
    
    async def _refresh_and_store(self, token: UserOAuthToken) -> UserOAuthToken:
        """Refresh token and store the new one"""
        new_token = await self.refresh_strategy.refresh_token(token, self.config)
        await self.store_token(new_token)
        return new_token
    
    def create_credentials_dict(self, token: UserOAuthToken) -> Dict[str, Any]:
        """
        Create a credentials dictionary for use with API clients
        
        Returns dict with all necessary fields for automatic refresh
        """
        return {
            'access_token': token.access_token,
            'refresh_token': token.refresh_token,
            'token_type': token.token_type,
            'expires_at': token.expires_at.timestamp() if token.expires_at else None,
            'scope': token.scope,
            # Provider-specific fields
            'client_id': self.config.get('client_id'),
            'client_secret': self.config.get('client_secret'),
            'token_uri': self.refresh_strategy.token_url if hasattr(self.refresh_strategy, 'token_url') else None
        }


def get_refresh_strategy(provider_id: str, config: Dict[str, Any]) -> TokenRefreshStrategy:
    """
    Get the appropriate refresh strategy for a provider
    
    Args:
        provider_id: Provider identifier
        config: Provider configuration
        
    Returns:
        TokenRefreshStrategy instance
    """
    strategies = {
        'google': GoogleRefreshStrategy,
        # Add more providers here
        # 'slack': SlackRefreshStrategy,
        # 'microsoft': MicrosoftRefreshStrategy,
    }
    
    strategy_class = strategies.get(provider_id)
    if strategy_class:
        if provider_id == 'google':
            return strategy_class()
        # Add provider-specific initialization as needed
    
    # Default to standard OAuth2 strategy
    token_url = config.get('token_url')
    if not token_url:
        raise ValueError(f"No token URL configured for provider {provider_id}")
    
    return OAuth2RefreshStrategy(token_url)