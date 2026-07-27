import hashlib
import os
import time
from functools import lru_cache
from typing import Any, Dict, Optional

import requests
import structlog
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# HTTP Bearer token security scheme
security = HTTPBearer()

logger = structlog.get_logger(__name__)

# Token validation cache (token_hash -> {payload, expires_at})
_token_cache = {}
CACHE_DURATION_SECONDS = 300  # 5 minutes


def _get_token_hash(token: str) -> str:
    """Create a hash of the token for cache key (don't store full token)"""
    return hashlib.sha256(token.encode()).hexdigest()[:32]


def _is_cache_valid(cache_entry: Dict) -> bool:
    """Check if cached token validation is still valid"""
    return time.time() < cache_entry.get("expires_at", 0)


def _cache_token_validation(token: str, payload: Dict[str, Any]) -> None:
    """Cache a successful token validation"""
    token_hash = _get_token_hash(token)
    _token_cache[token_hash] = {
        "payload": payload,
        "expires_at": time.time() + CACHE_DURATION_SECONDS,
    }

    # Clean up expired cache entries (simple cleanup)
    current_time = time.time()
    expired_keys = [
        k for k, v in _token_cache.items() if v.get("expires_at", 0) < current_time
    ]
    for key in expired_keys:
        _token_cache.pop(key, None)


def _get_cached_token_validation(token: str) -> Optional[Dict[str, Any]]:
    """Get cached token validation if still valid"""
    token_hash = _get_token_hash(token)
    cache_entry = _token_cache.get(token_hash)

    if cache_entry and _is_cache_valid(cache_entry):
        logger.debug("Using cached token validation", token_hash=token_hash)
        return cache_entry["payload"]

    return None


class UnauthorizedException(HTTPException):
    def __init__(self, detail: str, **kwargs):
        """Returns HTTP 403"""
        super().__init__(status.HTTP_403_FORBIDDEN, detail=detail)


class UnauthenticatedException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Requires authentication"
        )


class Auth0Config:
    """Auth0 configuration settings"""

    def __init__(self):
        self.domain = os.getenv("AUTH0_DOMAIN")
        self.algorithms = ["RS256"]

        if not self.domain:
            raise ValueError("AUTH0_DOMAIN environment variable is required")


@lru_cache(maxsize=1)
def get_auth0_config() -> Auth0Config:
    """Get cached Auth0 configuration"""
    return Auth0Config()


class VerifyToken:
    """Does all the token verification using python-jose"""

    def __init__(self):
        self.config = get_auth0_config()

    def verify(self, token: str) -> Dict[str, Any]:
        """Verify Auth0 JWT/JWE token by calling Auth0 server"""
        try:
            # Check cache first (works for both JWT and JWE)
            cached_payload = _get_cached_token_validation(token)
            if cached_payload:
                logger.info(
                    "Token validated from cache", user_id=cached_payload.get("sub")
                )
                return cached_payload

            # For all tokens (JWT and JWE), validate via Auth0 userinfo endpoint
            # This is simpler and more reliable than local verification
            return self._validate_with_auth0(token)

        except Exception as e:
            logger.error(
                "Unexpected error during token verification",
                error=str(e),
                exc_info=True,
            )
            raise UnauthenticatedException()

    def _validate_with_auth0(self, token: str) -> Dict[str, Any]:
        """Validate any token (JWT/JWE) by calling Auth0 server"""
        try:
            userinfo_url = f"https://{self.config.domain}/userinfo"
            headers = {"Authorization": f"Bearer {token}"}

            logger.info("Validating token with Auth0 server")
            response = requests.get(userinfo_url, headers=headers, timeout=10)

            if response.status_code == 200:
                userinfo = response.json()

                # Create minimal payload with just essential claims
                payload = {
                    "iss": f"https://{self.config.domain}/",
                    "sub": userinfo.get("sub"),  # Just user ID, essential for auth
                    "exp": int(time.time()) + 3600,  # 1 hour from now
                    "iat": int(time.time()),
                }

                # Cache the successful validation
                _cache_token_validation(token, payload)

                logger.info(
                    "Token validated by Auth0 server", user_id=payload.get("sub")
                )
                return payload
            else:
                logger.error(
                    "Auth0 server rejected token", status_code=response.status_code
                )
                raise UnauthenticatedException()

        except requests.RequestException as e:
            logger.error("Failed to contact Auth0 server", error=str(e))
            raise UnauthenticatedException()
        except Exception as e:
            logger.error("Error validating token with Auth0", error=str(e))
            raise UnauthenticatedException()

    def __call__(self, token: str) -> Dict[str, Any]:
        """Make the class callable for use with FastAPI Security"""
        return self.verify(token)


# Global instance
token_verifier = VerifyToken()


def extract_user_id(token_payload: Dict[str, Any]) -> str:
    """Extract user ID from Auth0 token payload"""
    # Auth0 typically uses 'sub' (subject) claim for user ID
    user_id = token_payload.get("sub")
    if not user_id:
        raise UnauthenticatedException()
    return user_id


async def get_token_payload(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> Dict[str, Any]:
    """
    Security dependency to verify Auth0 JWT token and return payload.
    Use this when you need the full token payload.
    """
    token = credentials.credentials
    payload = token_verifier.verify(token)
    return payload


async def get_current_user_id(
    token_payload: Dict[str, Any] = Depends(get_token_payload),
) -> str:
    """
    Security dependency to get the current authenticated user's ID.
    Use this when you only need the user ID.
    """
    return extract_user_id(token_payload)
