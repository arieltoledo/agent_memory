from typing import NewType
from uuid import UUID, uuid4

OpaqueId = NewType("OpaqueId", UUID)

def new_id() -> UUID:
    """Create a random UUID4; identifiers never derive from content."""
    return uuid4()
