"""Authorization boundary for memory operations."""

from .models import AuthContext, MemoryDomain, MemoryRecord


class MemoryAuthorizationError(PermissionError):
    """Raised when a memory operation is not authorized."""


def authorize(context: AuthContext, domain: MemoryDomain,
              session_id: str | None = None, record: MemoryRecord | None = None) -> None:
    if not isinstance(context, AuthContext) or not context.authenticated or not context.user_id:
        raise MemoryAuthorizationError("authenticated security context required")
    if record is not None and record.owner_id != context.user_id:
        raise MemoryAuthorizationError("memory ownership check failed")
    if domain == MemoryDomain.VENNELA_CORE and "memory:core" not in context.scopes:
        raise MemoryAuthorizationError("protected core scope required")
    if domain == MemoryDomain.SESSION:
        requested = session_id or (record.session_id if record else None)
        if not requested or requested != context.session_id:
            raise MemoryAuthorizationError("session ownership check failed")
