"""
Gate 2: Role-Based Tool Authorization (Cedar).

Gate 2 is this architecture's Policy Enforcement Point (PEP): it does not
decide anything itself, it forwards principal/action/resource to Cedar
(the decoupled Policy Decision Point) and enforces the binary decision
Cedar returns. Argument content is not inspected here, that's Gate 4.
"""

from dataclasses import dataclass
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


def evaluate_gate2(req: Gate2Request) -> None:
    request = {
        "principal": req.principal,
        "action": req.action,
        "resource": req.resource,
        "context": {},
    }
    result = is_authorized(request, POLICIES, req.entities)
    if result.decision != Decision.Allow:
        raise Gate2Denied(
            f"Cedar denied: {req.principal} {req.action} {req.resource}"
        )