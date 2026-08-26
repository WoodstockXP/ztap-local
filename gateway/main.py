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

Every gate's decision is written to gateway/audit_log.py's structured
JSON-lines log, including per-gate latency, this is what feeds Frame 3's
performance numbers and the eval harness's blocking-rate reports.

Run with:
    uvicorn gateway.main:app --reload
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

from .audit_log import audit_log, new_request_id
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

# Which agent identity this gateway deployment fronts. A deployment-time
# constant, not something the (untrusted) caller can assert per request,
# since letting a caller self-declare its own agent scope would defeat
# the whole point of scoping it. Real agent identity issuance (a separate
# credential, distinct from the user's OAuth token) is future work, this
# is a named, deliberate simplification for now, matching the pattern
# used for Gate 1's DPoP work: build something real and be explicit
# about what's still deferred.
AGENT_ID = os.environ.get("ZTAP_AGENT_ID", "invoice-agent-v2")

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
    request_id = new_request_id()
    pipeline_start = time.perf_counter()

    def log(gate: str, decision: str, detail: str, latency_ms: float, **extra) -> None:
        audit_log(
            request_id,
            gate,
            decision,
            detail,
            action=body.action,
            resource_id=body.resource_id,
            latency_ms=round(latency_ms, 3),
            **extra,
        )

    if not authorization.startswith("DPoP "):
        log("GATE1", "DENY", "Authorization header missing DPoP scheme", 0.0)
        raise HTTPException(status_code=403, detail=GENERIC_DENIAL)
    access_token = authorization.removeprefix("DPoP ")

    set_security_context(SecurityContext(raw_token=access_token, raw_dpop_proof=dpop))

    # --- Gate 1: Authentication and Tenant Resolution ---
    gate_start = time.perf_counter()
    try:
        gate1 = evaluate_gate1(http_method=request.method, http_url=str(request.url))
    except Gate1Denied as exc:
        log("GATE1", "DENY", str(exc), (time.perf_counter() - gate_start) * 1000)
        raise HTTPException(status_code=403, detail=GENERIC_DENIAL)
    log(
        "GATE1",
        "ALLOW",
        f"authenticated as {gate1.principal} (tenant={gate1.tenant})",
        (time.perf_counter() - gate_start) * 1000,
        tenant=gate1.tenant,
        principal=gate1.principal,
    )

    principal_ref = f'User::"{gate1.principal}"'
    action_ref = f'Action::"{body.action}"'
    resource_ref = f'Record::"{body.resource_id}"'

    # --- Gate 2: Role-Based Tool Authorization (Cedar) ---
    gate_start = time.perf_counter()
    try:
        evaluate_gate2(
            Gate2Request(
                principal=principal_ref,
                action=action_ref,
                resource=resource_ref,
                entities=ENTITIES,
                context={"agent": {"__entity": {"type": "Agent", "id": AGENT_ID}}},
            )
        )
    except Gate2Denied as exc:
        log(
            "GATE2",
            "DENY",
            str(exc),
            (time.perf_counter() - gate_start) * 1000,
            tenant=gate1.tenant,
            principal=gate1.principal,
        )
        raise HTTPException(status_code=403, detail=GENERIC_DENIAL)
    log(
        "GATE2",
        "ALLOW",
        f"{gate1.principal} authorized for {body.action} (agent={AGENT_ID})",
        (time.perf_counter() - gate_start) * 1000,
        tenant=gate1.tenant,
        principal=gate1.principal,
    )

    # --- Gate 3: Session Envelope Enforcement ---
    gate_start = time.perf_counter()
    try:
        evaluate_gate3(tenant=gate1.tenant, principal=gate1.principal, action=body.action)
    except Gate3Denied as exc:
        log(
            "GATE3",
            "DENY",
            str(exc),
            (time.perf_counter() - gate_start) * 1000,
            tenant=gate1.tenant,
            principal=gate1.principal,
        )
        raise HTTPException(status_code=403, detail=GENERIC_DENIAL)
    log(
        "GATE3",
        "ALLOW",
        "within session envelope threshold",
        (time.perf_counter() - gate_start) * 1000,
        tenant=gate1.tenant,
        principal=gate1.principal,
    )

    # --- Gate 4: Schema Conformance Validation ---
    gate_start = time.perf_counter()
    try:
        validated_args = evaluate_gate4(body.action, body.args)
    except Gate4Denied as exc:
        log(
            "GATE4",
            "DENY",
            str(exc),
            (time.perf_counter() - gate_start) * 1000,
            tenant=gate1.tenant,
            principal=gate1.principal,
        )
        raise HTTPException(status_code=403, detail=GENERIC_DENIAL)
    log(
        "GATE4",
        "ALLOW",
        "arguments well-formed",
        (time.perf_counter() - gate_start) * 1000,
        tenant=gate1.tenant,
        principal=gate1.principal,
    )

    total_latency_ms = (time.perf_counter() - pipeline_start) * 1000
    log(
        "ALL_GATES",
        "ALLOW",
        f"{gate1.principal} -> {body.action} on {body.resource_id}",
        total_latency_ms,
        tenant=gate1.tenant,
        principal=gate1.principal,
    )
    return {
        "decision": "ALLOW",
        "action": body.action,
        "validated_args": validated_args.model_dump(),
    }