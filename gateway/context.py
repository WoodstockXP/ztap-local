"""
Security Context / ContextVars layer (Frame 1).

Pure plumbing, not a security control. Threads the raw token and (later)
DPoP proof through the async runtime so downstream gates can read them
without global state or race conditions between concurrent requests.
Nothing here is cryptographically verified; that happens in Gate 1.
"""

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional


@dataclass
class SecurityContext:
    raw_token: Optional[str] = None
    raw_dpop_proof: Optional[str] = None  # unused until real Gate 1 lands

    # populated once Gate 1 actually verifies something:
    verified_principal: Optional[str] = None
    verified_tenant: Optional[str] = None


_security_context: ContextVar[SecurityContext] = ContextVar("security_context")


def set_security_context(ctx: SecurityContext) -> None:
    _security_context.set(ctx)


def get_security_context() -> SecurityContext:
    try:
        return _security_context.get()
    except LookupError as exc:
        raise RuntimeError(
            "No SecurityContext set for this request. "
            "set_security_context() must run before any gate executes."
        ) from exc