# ADR-0008: Docker Compose for local development, Kubernetes deferred to benchmarks

**Status:** Accepted

## Context

The outline's Phase 4 milestone calls for a fully working local version of
the system before any cloud or Kubernetes work begins, and the Jul 20th
feedback's answer to "how can a prototype be implemented" explicitly
recommended building a local Docker Compose harness first: a gateway
process, local Cedar, a local Keycloak instance, and a stub API, all
runnable and testable in a single integration loop before any
Infrastructure-as-Code or Kubernetes work starts.

## Decision

All local development work (Keycloak, the gateway, the agent, the
evaluation harness) runs against services reachable on `localhost`, via
Docker Compose for Keycloak and plain local processes for everything else.
A managed Kubernetes cluster is reserved specifically for the final Bridge
versus Silo benchmark runs (outline Phases 5 and 6), not used during
iterative development.

## Alternatives Considered

- **Developing directly against Kubernetes from the start** (for example
  `kind` or `k3d` locally): rejected as premature complexity for the
  current phase. The four-gate pipeline and Cedar policies needed to be
  built and iterated on quickly first; validating gate logic does not
  require Kubernetes's namespace or networking model, only the
  isolation-depth comparison that is the paper's actual empirical
  contribution does.

## Consequences

**Positive**

- Fast iteration throughout Phase 4: restarting the gateway or Keycloak
  takes seconds, not a cluster redeploy, which mattered directly while
  debugging real issues (DPoP binding, Gate 3 state leakage across test
  cases, and others) that needed many quick iterations to fix correctly.
- Defers genuinely hard infrastructure work (per-tenant node pools,
  Cilium NetworkPolicy, gVisor sandboxing) to when it is actually needed,
  keeping early debugging cycles cheap and focused on application-level
  correctness first.

**Negative**

- Local Docker Compose testing cannot validate anything about the actual
  Bridge or Silo network-isolation claim; that is the entire point of the
  later Kubernetes phase and is not yet exercised at all by the current
  build.
- Some issues only manifest under real network policy enforcement or
  multi-node scheduling and will not surface until that phase begins,
  meaning the current "fully working local version" milestone, while
  real, does not de-risk the Kubernetes-specific portion of the project.
