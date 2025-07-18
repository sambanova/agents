import os
from functools import lru_cache
from typing import Any, Dict, Optional

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidTokenError,
)

# HTTP Bearer token security scheme
security = HTTPBearer()


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
        self.audience = os.getenv("AUTH0_AUDIENCE")
        self.algorithms = ["RS256"]

        if not self.domain:
            raise ValueError("AUTH0_DOMAIN environment variable is required")


@lru_cache(maxsize=1)
def get_auth0_config() -> Auth0Config:
    """Get cached Auth0 configuration"""
    return Auth0Config()


class VerifyToken:
    """Does all the token verification using PyJWT"""

    def __init__(self):
        self.config = get_auth0_config()

        # This gets the JWKS from a given URL and does processing so you can
        # use any of the keys available
        jwks_url = f"https://{self.config.domain}/.well-known/jwks.json"
        self.jwks_client = jwt.PyJWKClient(jwks_url)

    def verify(self, token: str) -> Dict[str, Any]:
        """Verify Auth0 JWT token and return claims"""
        try:
            # Get the signing key from the JWKS
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)

            # Verify token
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=self.config.algorithms,
                issuer=f"https://{self.config.domain}/",
            )
            return payload
        except ExpiredSignatureError:
            raise UnauthenticatedException()
        except InvalidIssuerError:
            raise UnauthorizedException("Invalid issuer")
        except InvalidTokenError as e:
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
