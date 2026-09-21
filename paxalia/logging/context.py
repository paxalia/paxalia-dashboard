"""Request-scoped context for Paxalia observability.

This module deliberately uses ContextVar rather than thread-locals so the same
API behaves correctly in synchronous Django code and in async-capable stacks.
"""
from contextvars import ContextVar


_REQUEST_CONTEXT = ContextVar("paxalia_request_context", default={})


def get_context():
    """Return a shallow copy of the current request context."""
    return dict(_REQUEST_CONTEXT.get() or {})


def set_context(values):
    """Replace the current context and return the ContextVar token."""
    return _REQUEST_CONTEXT.set(dict(values or {}))


def reset_context(token):
    """Restore the context represented by *token*."""
    _REQUEST_CONTEXT.reset(token)
