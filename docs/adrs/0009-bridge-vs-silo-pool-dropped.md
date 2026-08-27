# ADR-0009: Bridge vs Silo as the isolation-depth comparison axis, Pool dropped

**Status:** Accepted

## Context

AWS AgentCore names a three-point isolation spectrum: Pool (shared
runtime, shared network), Bridge (shared runtime, isolated network per
tenant), and Silo (fully dedicated runtime and network per tenant),
explicitly framed as a cost, isolation, and complexity trade-off without a
published benchmark quantifying it. This project's core contribution
targets exactly that unquantified trade-off.

## Decision

Compare exactly two configurations, Bridge and Silo, under identical
four-gate enforcement logic and identical Cedar policies. Pool is out of
scope.

## Alternatives Considered

- **Comparing all three points (Pool, Bridge, Silo)**: this was the
  original plan in early project files. Cut specifically to protect the
  six-week timeline: a three-way comparison roughly triples the
  infrastructure provisioning and benchmark-running burden, and Pool is
  strictly weaker isolation than Bridge on every dimension that matters
  here, so its main empirical contribution would have been a third
  latency and cost data point along an already-implied trend line, not a
  qualitatively new isolation finding.

## Consequences

**Positive**

- Keeps RQ1 and H3's empirical scope achievable inside a fixed timeline.
- Two configurations means every benchmark run happens twice rather than
  three times, materially reducing the cloud infrastructure time and cost
  risk that outline.md names explicitly as a project risk.

**Negative**

- The full Pool-Bridge-Silo spectrum AWS actually names is not fully
  empirically covered; only two of its three points are measured. This
  should be stated explicitly as a scope limitation in the paper rather
  than left implicit, since a reader familiar with AgentCore's own
  framing might otherwise expect all three to be addressed.

## Note

Some earlier project documentation (the outline's Phase 3 milestone) still
describes this as "Bridge vs. Silo on AWS EKS." That phrasing predates
ADR-0001's self-hosted decision and is stale; the actual target is a
self-hosted, cloud-agnostic managed Kubernetes cluster, not EKS
specifically. Worth reconciling in the outline before it is cited in the
paper as-is.
