"""Legacy import compatibility for the Basic Memory API."""

from .api import MemoryAPI
from .models import AuthContext
from .repository import InMemoryMemoryRepository

_api = MemoryAPI(InMemoryMemoryRepository())


def add_chat(user_id, role, message, **_metadata):
    """Store a chat event through the controlled API."""
    return _api.create(AuthContext(user_id=user_id), message, "Event")
