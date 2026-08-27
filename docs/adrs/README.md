# Architecture Decision Records: ZTAP (Zero-Trust Agent Perimeter)

This directory records the significant architectural decisions made while
building the ZTAP prototype, why each choice was made, what alternatives
were considered, and what trade-offs were accepted. These are written
after the fact, reconstructed from the actual build process, not drafted
speculatively before implementation, so "Consequences" sections include
things that were only discovered once the decision was already load-bearing
(for example, ADR-0005's note on gate preemption, found while building the
evaluation harness, not anticipated when the four-gate pipeline was designed).

| ID | Title | Status |
|---|---|---|
| [0001](0001-self-hosted-cloud-agnostic-infrastructure.md) | Self-hosted, cloud-agnostic infrastructure (no AWS-managed services) | Accepted |
| [0002](0002-keycloak-as-identity-provider.md) | Keycloak as the Identity Provider | Accepted |
| [0003](0003-dpop-over-mtls.md) | DPoP (RFC 9449) over mTLS for token binding | Accepted |
| [0004](0004-cedar-as-policy-engine.md) | Cedar as the policy engine for Gate 2 | Accepted |
| [0005](0005-four-independent-gates.md) | Four independent sequential gates instead of single-entity authorization | Accepted |
| [0006](0006-sliding-window-counters-gate3.md) | Sliding-window counters for Gate 3, not statistical/ML anomaly detection | Accepted |
| [0007](0007-self-hosted-ollama-llama32-3b.md) | Self-hosted Ollama with Llama 3.2 3B for agent inference | Accepted |
| [0008](0008-docker-compose-then-kubernetes.md) | Docker Compose for local development, Kubernetes deferred to benchmarks | Accepted |
| [0009](0009-bridge-vs-silo-pool-dropped.md) | Bridge vs Silo as the isolation-depth comparison axis, Pool dropped | Accepted |
| [0010](0010-single-shared-agent-process.md) | One shared agent process serving all tenants | Accepted |
| [0011](0011-acting-as-agent-via-context.md) | User acting_as Agent modeled via Cedar context, not a compound principal | Accepted |
| [0012](0012-agent-identity-deployment-constant.md) | Agent identity as a gateway deployment constant, not self-asserted | Accepted |
| [0013](0013-ropc-for-local-testing-only.md) | Resource Owner Password Credentials for local testing only | Accepted |

## A note on scope

These cover architecture and technology-choice decisions. Evaluation
methodology choices (attack corpus design, baseline configurations, the
harness's log-correlation approach) are documented inline in `eval/` and
in the paper's Methodology and Evaluation sections instead, since they are
closer to experimental design than system architecture, and change more
readily as the evaluation matures.
