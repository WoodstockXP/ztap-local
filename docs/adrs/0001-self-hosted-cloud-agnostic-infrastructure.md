# ADR-0001: Self-hosted, cloud-agnostic infrastructure (no AWS-managed services)

**Status:** Accepted

## Context

The project's stated contribution is a benchmark comparing isolation depth
(Bridge vs Silo) under identical enforcement logic, quantifying a cost and
latency trade-off that AWS's own AgentCore documentation names but does not
publish numbers for. If the prototype itself were built on AWS-managed
services (Cognito, Bedrock AgentCore, managed OAuth), any measured
difference between configurations would be entangled with AWS-specific
implementation details, and the results would not be reproducible without
an AWS account, quota approval, and ongoing billing.

## Decision

No AWS-managed services appear anywhere in the stack. Identity (Keycloak),
policy evaluation (Cedar), inference (Ollama), and the gateway itself are
all self-hosted, first via Docker Compose locally, later on a managed
Kubernetes cluster for benchmarks, kept described in cloud-agnostic terms
(for example "Managed Kubernetes Cluster" rather than a specific provider's
product name) in diagrams and documentation.

## Alternatives Considered

- **AWS Cognito plus Bedrock AgentCore**: rejected. Ties results to one
  vendor's primitives, cannot be reproduced without an AWS account, and
  would conflate "isolation depth" findings with "AWS-specific
  implementation choices," undermining the paper's own stated
  contribution.
- **GCP equivalent managed services**: rejected for the same
  reproducibility and vendor-coupling reasons.

## Consequences

**Positive**

- Reproducible without cloud billing or quota constraints, removing a
  confound the outline itself names explicitly.
- Findings are not tied to one vendor's specific isolation primitives, so
  they generalize better as a statement about the Bridge/Silo pattern
  itself rather than about AWS's implementation of it.

**Negative**

- Does not validate findings against a managed provider's own isolation
  primitives directly. This is a named, accepted trade-off, not an
  oversight, worth stating plainly in Limitations.
- More setup burden: components a managed service would provide out of
  the box (identity provider, policy store) had to be configured and
  version-controlled by hand (see ADR-0002, ADR-0004).
