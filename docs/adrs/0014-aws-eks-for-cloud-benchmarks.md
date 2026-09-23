# ADR-0014: AWS EKS as the managed Kubernetes provider for cloud benchmarks

**Status:** Accepted

## Context

ADR-0001 established self-hosted, cloud-agnostic infrastructure specifically to avoid AWS's bespoke agent-security products (Cognito, Bedrock AgentCore) confounding isolation-depth findings with vendor-specific primitives. ADR-0008 deferred Kubernetes work to a later benchmark phase without specifying a provider. ADR-0009's Note flagged that outline.md's "Bridge vs. Silo on AWS EKS" phrasing predates ADR-0001 and needed reconciling before being cited in the paper as-is. Phase 6 required standing up both topologies on a real managed Kubernetes cluster, real EC2 instances, real network boundaries, real cost, none of which kind's Docker-in-Docker nodes can represent. An AWS account was already available, narrowing the practical provider choice.

## Decision

Deploy both Bridge and Silo to AWS EKS for the cloud benchmark phase, via Terraform. This resolves ADR-0009's flagged tension by narrowing ADR-0001's scope explicitly here: ADR-0001's "no AWS-managed services" decision refers to AWS's bespoke agent-identity and agent-runtime products that would couple the research findings themselves, what counts as a policy engine, what counts as identity binding, to one vendor's implementation. It does not extend to the underlying managed Kubernetes control plane the self-hosted stack runs on top of. Every component the research claims actually depend on, Cilium for network policy, Keycloak for identity, Cedar for policy evaluation, Ollama for inference, the FastAPI gateway itself, remains self-hosted open-source software, unchanged from local, and portable to any other Kubernetes provider without modification.

## Alternatives Considered

- **A different cloud's managed Kubernetes (GKE, AKS)**: would satisfy the same cloud-agnostic-at-the-workload-level principle equally well. Not chosen because no account access existed for either, and account and quota friction was already a significant, unplanned time cost even on the one account that was available (see ADR-0017).
- **Self-managed Kubernetes on raw EC2 instances (kubeadm or similar), avoiding a managed control plane entirely**: the most literal reading of "no AWS-managed services." Rejected as materially increasing the infrastructure-build burden (control plane HA, etcd, upgrades) for a six-day implementation window, with no corresponding benefit to the research questions, which concern tenant isolation depth, not control-plane management.

## Consequences

**Positive**

- Real EC2 instances, real VPC and subnet boundaries, and real per-instance cost replace kind's Docker-in-Docker nodes, letting RQ1 and RQ3's cost and isolation-depth claims be measured against actual infrastructure rather than a local approximation.
- Every self-hosted component the research findings depend on remains genuinely portable; nothing about Gates 1 through 4, Cedar policy, or the isolation architecture itself is EKS-specific.

**Negative**

- The specific numbers gathered in Phase 6 (cost, Tier 2 duration) are AWS EKS numbers, not validated against a second provider. The Bridge/Silo isolation-depth pattern is argued to generalize, but only one managed Kubernetes provider's actual behavior was measured, worth stating explicitly as a limitation rather than left implicit.
- A large share of Phase 6's real time went to account- and platform-specific friction unrelated to the research questions themselves: a Free Plan restriction blocking On-Demand instances (ADR-0017), a denied GPU quota request, containerd's config path changing between major versions and gVisor's own release format changing mid-build (ADR-0018), Cilium's ENI-mode masquerade defaults needing correction. None of this is a finding about the Bridge/Silo pattern; it is infrastructure noise specific to this account, this AMI, and this week, and should not be read back into the paper as though it were.
