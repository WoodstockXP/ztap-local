"""
Gate 2: Role-Based Tool Authorization (Cedar).

Gate 2 is this architecture's Policy Enforcement Point (PEP): it does not
decide anything itself, it forwards principal/action/resource/context to
Cedar (the decoupled Policy Decision Point) and enforces the binary
decision Cedar returns. Argument content is not inspected here, that's
Gate 4.

principal is the human user (the AuthZen "Subject"). The acting agent's
own, possibly narrower, scope travels in context (the AuthZen "Context"),
per the Jul 20th feedback, letting the policy restrict what an agent can
do on a user's behalf independently of what the user themself is allowed.
See gate2.cedar for the actual policy logic.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from cedarpy import Decision, is_authorized

POLICIES = (Path(__file__).parent / "policies" / "gate2.cedar").read_text()


class Gate2Denied(Exception):
    pass


@dataclass
class Gate2Request:
    principal: str  # e.g. 'User::"alice"'
    action: str  # e.g. 'Action::"readRecord"'
    resource: str  # e.g. 'Record::"rec-001"'
    entities: List[Dict[str, Any]]
    context: Dict[str, Any] = field(default_factory=dict)


def evaluate_gate2(req: Gate2Request) -> None:
    request = {
        "principal": req.principal,
        "action": req.action,
        "resource": req.resource,
        "context": req.context,
    }
    result = is_authorized(request, POLICIES, req.entities)
    if result.decision != Decision.Allow:
        raise Gate2Denied(
            f"Cedar denied: {req.principal} {req.action} {req.resource} "
            f"(context={req.context})"
        )