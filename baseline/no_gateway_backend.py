"""
No-gateway baseline (Evaluation Plan): the agent talks directly to a stub
backend with zero enforcement. No Gate 1 auth, no Gate 2 Cedar, no Gate 3
session envelope, no Gate 4 schema validation, nothing. This exists
purely as a comparison point to measure what the four-gate pipeline
actually buys, per H1: "providing stronger security guarantees than an
approach that relies on the LLM to respect permissions."

Deliberately naive: this does not simulate a realistic-but-insecure
system, it simulates the complete absence of a security layer, so the
difference between this and the full pipeline isolates what the pipeline
contributes rather than conflating it with some other design choice.

Important for a fair comparison: this module does NOT import anything
from gateway/. Reusing the real entities or record store there would
blur the line between "no gateway" and "gateway with some checks
skipped", the two need to be genuinely different code paths, not the
same code with flags off, or the baseline comparison stops meaning what
it claims to mean.
"""

from typing import Any, Dict

_RECORDS: Dict[str, Dict[str, Any]] = {
    "rec-001": {"tenant": "tenant-a", "amount": 100},
    "rec-002": {"tenant": "tenant-b", "amount": 200},
}


def reset() -> None:
    """Test/harness helper to restore initial state between runs."""
    global _RECORDS
    _RECORDS = {
        "rec-001": {"tenant": "tenant-a", "amount": 100},
        "rec-002": {"tenant": "tenant-b", "amount": 200},
    }


def read_record(resource_id: str) -> Dict[str, Any]:
    if resource_id not in _RECORDS:
        return {"decision": "ALLOW (no gateway)", "error": "not found"}
    return {"decision": "ALLOW (no gateway)", "record": dict(_RECORDS[resource_id])}


def update_record(resource_id: str, amount: Any) -> Dict[str, Any]:
    # No type check, no bounds check, no injection filtering: this is the
    # point. Whatever the caller sends is written straight through.
    if resource_id not in _RECORDS:
        _RECORDS[resource_id] = {"tenant": "unknown", "amount": amount}
    else:
        _RECORDS[resource_id]["amount"] = amount
    return {"decision": "ALLOW (no gateway)", "record": dict(_RECORDS[resource_id])}