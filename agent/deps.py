"""
Dependency injection for the agent. Pydantic AI threads one instance of
this through every tool call via RunContext, this is how a specific
user's GatewaySession (and therefore their bound token, tenant, and
identity) reaches the tools without any global or module-level state.
"""

from dataclasses import dataclass

from .gateway_session import GatewaySession


@dataclass
class AgentDeps:
    gateway: GatewaySession