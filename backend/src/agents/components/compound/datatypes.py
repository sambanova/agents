from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class Assistant(BaseModel):
    config: dict
    """The assistant config."""


class Thread(BaseModel):
    thread_id: str
    """The ID of the thread."""
    user_id: str
    """The ID of the user that owns the thread."""
    name: str
    """The name of the thread."""
    updated_at: datetime
    """The last time the thread was updated."""
    metadata: Optional[dict] = None


class User(BaseModel):
    user_id: str
    """The ID of the user."""
    sub: str
    """The sub of the user (from a JWT token)."""
    created_at: datetime
    """The time the user was created."""
