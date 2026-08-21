"""
Gate 3: Session Envelope Enforcement.

Tracks how often a given (tenant, principal, action) combination has been
called within a recent time window and denies once a threshold is
crossed. This targets H2's aggregate-attack pattern: a sequence of
individually-authorized calls, each one clears Gates 1, 2, and 4 on its
own, that collectively constitute unauthorized behavior (e.g. reading
many records in rapid succession to exfiltrate data, when a single read
would never trigger anything on its own).

Deliberately a simple sliding-window counter, not a statistical or
ML-based anomaly detector, per the Aug 10th feedback's framing: this
narrows the aggregate-pattern gap, it does not claim to close it, and it
keeps the architecture's decisions provable and auditable rather than
trading that away for UEBA-style scoring.

Unlike Gates 1/2/4, this gate's decision depends on request history, so
it needs a store. That store is process-local by design: the outline
flags a shared session store across tenants as the one dependency that
would quietly undermine the Silo configuration's isolation claim. It
isn't shared here (this module's store lives in this process only), and
Silo's design, a fully separate gateway process per tenant, keeps it that
way structurally. Worth re-confirming when the Silo build happens rather
than assumed.

Toggleable via ZTAP_GATE3_ENABLED, since the Evaluation Plan's baselines
require comparing "Gates 1/2/4 only" against the full four-gate pipeline
to isolate what Gate 3 actually adds.
"""

import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, List, Tuple

# (max_calls, window_seconds) per action. Deliberately stricter for the
# mutating action than the read action: a burst of reads is more
# plausibly legitimate (a dashboard, a report) than a burst of writes.
# These are starting points, not validated numbers, tune them once the
# adversarial test harness exists and you can measure false-positive
# rate against legitimate bursty usage (see outline's "Session envelope
# thresholds" trade-off).
DEFAULT_THRESHOLDS: Dict[str, Tuple[int, int]] = {
    "readRecord": (10, 60),
    "updateRecord": (3, 60),
}
FALLBACK_THRESHOLD: Tuple[int, int] = (5, 60)

GATE3_ENABLED = os.environ.get("ZTAP_GATE3_ENABLED", "true").strip().lower() not in (
    "false",
    "0",
    "no",
)


class Gate3Denied(Exception):
    pass


@dataclass
class SessionEnvelopeStore:
    """Sliding-window call counter keyed by (tenant, principal, action).
    Process-local by design, see module docstring."""

    _calls: Dict[Tuple[str, str, str], List[float]] = field(
        default_factory=lambda: defaultdict(list)
    )
    _lock: Lock = field(default_factory=Lock)

    def check_and_record(self, tenant: str, principal: str, action: str) -> None:
        max_calls, window_seconds = DEFAULT_THRESHOLDS.get(action, FALLBACK_THRESHOLD)
        key = (tenant, principal, action)
        now = time.time()

        with self._lock:
            timestamps = self._calls[key]
            cutoff = now - window_seconds
            timestamps[:] = [t for t in timestamps if t > cutoff]

            if len(timestamps) >= max_calls:
                raise Gate3Denied(
                    f"Session envelope exceeded: {principal} made {len(timestamps)} "
                    f"{action} calls within {window_seconds}s (limit {max_calls})"
                )

            timestamps.append(now)

    def reset(self) -> None:
        """Test/debug helper, not used by the request path."""
        with self._lock:
            self._calls.clear()


# Process-local singleton: one gateway process, one store. Correct for
# Bridge (one shared gateway process across tenants, partitioned
# internally by the tenant key in the lookup) and stays correct for Silo
# as long as Silo remains one fully separate gateway process per tenant.
_store = SessionEnvelopeStore()


def evaluate_gate3(tenant: str, principal: str, action: str) -> None:
    if not GATE3_ENABLED:
        return
    _store.check_and_record(tenant, principal, action)