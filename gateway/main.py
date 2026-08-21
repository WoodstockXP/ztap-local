"""
Inline Policy Interceptor / Security Gateway (Frame 1 and Frame 2).

Wires all four gates into a sequential pipeline: a request must clear
each gate in order, and a failure at any gate blocks execution outright
with only a generic denial returned to the caller. The full reason is
logged to the audit sink instead, per Frame 1's separation between what
the (untrusted) caller sees and what gets recorded.
 
Gate order: authentication and tenant resolution (Gate 1), Cedar-based
role authorization (Gate 2), session envelope enforcement (Gate 3), then
schema conformance validation (Gate 4). Gate 3 can be disabled via
ZTAP_GATE3_ENABLED=false for the "Gates 1/2/4 only" baseline the
Evaluation Plan calls for; see gate3_session_envelope.py.

Run with:
    uvicorn gateway.main:app --reload
"""

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

from .context import SecurityContext, set_security_context
from .gate1_auth import Gate1Denied, evaluate_gate1
from .gate2_authorization import Gate2Denied, Gate2Request, evaluate_gate2
from .gate3_session_envelope import Gate3Denied, evaluate_gate3
from .gate4_schema import Gate4Denied, evaluate_gate4

app = FastAPI(title="Zero-Trust Agent Perimeter Gateway (local harness)")

# Stand-in for a real tenant/user directory. Gate 2 needs Cedar entities
# (attributes like which tenant a user or record belongs to) on every
# call; loading this static file is a placeholder for a real entity
# store once one exists.
ENTITIES = json.loads(
    (Path(__file__).parent / "policies" / "gate2_entities.json").read_text()
)

GENERIC_DENIAL = {"decision": "DENY", "detail": "Action not permitted"}


class InvokeRequest(BaseModel):
    action: str  # e.g. "readRecord", "updateRecord"
    resource_id: str  # e.g. "rec-001"
    args: Dict[str, Any]  # raw, unvalidated intent payload arguments


@app.post("/invoke")
def invoke(
    body: InvokeRequest,
    request: Request,
    authorization: str = Header(
        ..., description='RFC 9449 scheme: "DPoP <access_token>"'
    ),
    dpop: str = Header(..., description="DPoP proof JWT for this specific request"),
):
    if not authorization.startswith("DPoP "):
        _audit_log("GATE1", "DENY", "Authorization header missing DPoP scheme")
        raise HTTPException(status_code=403, detail=GENERIC_DENIAL)
    access_token = authorization.removeprefix("DPoP ")

    set_security_context(SecurityContext(raw_token=access_token, raw_dpop_proof=dpop))

    # --- Gate 1: Authentication and Tenant Resolution ---
    try:
        gate1 = evaluate_gate1(http_method=request.method, http_url=str(request.url))
    except Gate1Denied as exc:
        _audit_log("GATE1", "DENY", str(exc))
        raise HTTPException(status_code=403, detail=GENERIC_DENIAL)

    principal_ref = f'User::"{gate1.principal}"'
    action_ref = f'Action::"{body.action}"'
    resource_ref = f'Record::"{body.resource_id}"'

    # --- Gate 2: Role-Based Tool Authorization (Cedar) ---
    try:
        evaluate_gate2(
            Gate2Request(
                principal=principal_ref,
                action=action_ref,
                resource=resource_ref,
                entities=ENTITIES,
            )
        )
    except Gate2Denied as exc:
        _audit_log("GATE2", "DENY", str(exc))
        raise HTTPException(status_code=403, detail=GENERIC_DENIAL)

    # --- Gate 3: Session Envelope Enforcement ---
    try:
        evaluate_gate3(tenant=gate1.tenant, principal=gate1.principal, action=body.action)
    except Gate3Denied as exc:
        _audit_log("GATE3", "DENY", str(exc))
        raise HTTPException(status_code=403, detail=GENERIC_DENIAL)
 
    # --- Gate 4: Schema Conformance Validation ---
    try:
        validated_args = evaluate_gate4(body.action, body.args)
    except Gate4Denied as exc:
        _audit_log("GATE4", "DENY", str(exc))
        raise HTTPException(status_code=403, detail=GENERIC_DENIAL)

    _audit_log(
        "ALL_GATES", "ALLOW", f"{gate1.principal} -> {body.action} on {body.resource_id}"
    )
    return {
        "decision": "ALLOW",
        "action": body.action,
        "validated_args": validated_args.model_dump(),
    }


def _audit_log(gate: str, decision: str, detail: str) -> None:
    # Placeholder for the Append-Only Audit Log & Telemetry layer (Frame 2).
    # Prints for now; swap for real structured logging once you get to the Monitoring pillar.
    print(f"[AUDIT] gate={gate} decision={decision} detail={detail}")