"""
Shared result types and reporting helpers for the evaluation harness.
"""

from dataclasses import dataclass
from typing import List, Optional

from gateway.audit_log import read_entries


@dataclass
class HarnessResult:
    test_id: str
    description: str
    gate: Optional[str]
    expected: str
    actual: str
    passed: bool
    extra: Optional[str] = None


def print_summary(results: List[HarnessResult]) -> None:
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"[{status}] {r.test_id}: {r.description}")
        extra = f"  ({r.extra})" if r.extra else ""
        print(f"         expected={r.expected}  actual={r.actual}{extra}")

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    print()
    print(f"{passed}/{total} test cases passed")
    if passed < total:
        print("FAILURES:")
        for r in results:
            if not r.passed:
                print(f"  - {r.test_id}: {r.description}")


def blocking_rate_report(since: float, until: Optional[float] = None) -> None:
    """Read the structured audit log for a time window and print a
    blocking-rate + latency summary, independent of the harness's own
    pass/fail scoring, this is what the gateway itself actually recorded."""
    entries = read_entries(since=since, until=until)
    denials = [e for e in entries if e["decision"] == "DENY"]
    allows = [e for e in entries if e["decision"] == "ALLOW" and e["gate"] == "ALL_GATES"]

    print(f"\n=== Audit log summary ({len(entries)} entries) ===")
    by_gate = {}
    for e in denials:
        by_gate[e["gate"]] = by_gate.get(e["gate"], 0) + 1
    print("Denials by gate:")
    for gate, count in sorted(by_gate.items()):
        print(f"  {gate}: {count}")
    print(f"Fully allowed requests: {len(allows)}")

    latencies = [
        e["latency_ms"]
        for e in entries
        if e["gate"] == "ALL_GATES" and e.get("latency_ms") is not None
    ]
    if latencies:
        latencies.sort()
        n = len(latencies)
        mean = sum(latencies) / n
        p50 = latencies[n // 2]
        p95 = latencies[min(n - 1, int(n * 0.95))]
        print(
            f"End-to-end latency (allowed requests only): "
            f"mean={mean:.2f}ms p50={p50:.2f}ms p95={p95:.2f}ms n={n}"
        )