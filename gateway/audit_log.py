"""
Structured audit logging: Frame 2's Append-Only Audit Log & Telemetry
layer. Every gate decision is appended as one JSON line to
logs/gateway_audit.jsonl (in addition to the existing stdout print), so
the evaluation harness can compute blocking rates and latency stats
without scraping terminal output.

Append-only in spirit, not in guarantee: this process only ever appends,
never rewrites or deletes existing lines. Nothing here stops someone from
editing the file directly, a real tamper-evident store (write-once
storage, a hash chain) is out of scope for a local prototype, worth
naming as a limitation rather than implying stronger guarantees than
exist.
"""

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

LOG_PATH = Path(__file__).parent.parent / "logs" / "gateway_audit.jsonl"
LOG_PATH.parent.mkdir(exist_ok=True)


def new_request_id() -> str:
    return str(uuid.uuid4())


def audit_log(
    request_id: str,
    gate: str,
    decision: str,
    detail: str,
    *,
    tenant: Optional[str] = None,
    principal: Optional[str] = None,
    action: Optional[str] = None,
    resource_id: Optional[str] = None,
    latency_ms: Optional[float] = None,
) -> None:
    entry: Dict[str, Any] = {
        "timestamp": time.time(),
        "request_id": request_id,
        "gate": gate,
        "decision": decision,
        "detail": detail,
        "tenant": tenant,
        "principal": principal,
        "action": action,
        "resource_id": resource_id,
        "latency_ms": latency_ms,
    }
    print(f"[AUDIT] gate={gate} decision={decision} detail={detail}")
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def read_entries(since: Optional[float] = None, until: Optional[float] = None):
    """Read audit log entries, optionally filtered to a time window.
    Used by the harness to correlate log entries with a specific test
    case's run window."""
    if not LOG_PATH.exists():
        return []
    entries = []
    with open(LOG_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if since is not None and entry["timestamp"] < since:
                continue
            if until is not None and entry["timestamp"] > until:
                continue
            entries.append(entry)
    return entries