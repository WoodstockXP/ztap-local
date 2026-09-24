# ADR-0016: Silo's AWS isolation depth: per-tenant subnet and Security Groups within one VPC, not per-tenant VPCs

**Status:** Accepted

## Context

AWS's own Pool/Bridge/Silo framing (ADR-0009) describes Silo as having a fully dedicated runtime and network per tenant. Locally, Silo's isolation depth is expressed entirely through Kubernetes-native constructs, separate namespaces, Cilium NetworkPolicy default-deny, separate node labels, since kind has no concept of a VPC. On AWS, a literal reading of "dedicated network per tenant" would mean a fully separate VPC per tenant, with its own routing and no peering to the other tenant's VPC or to shared services like Ollama, materially increasing both the Terraform surface area and the operational risk within a fixed, short implementation window already showing first-time-on-EKS friction (see ADR-0014's Negative section).

## Decision

Silo's AWS deployment scopes its deepened network isolation to per-tenant subnets and per-tenant Security Groups within a single shared VPC (the `vpc` module's `subnet_per_tenant = true`), not separate VPCs. Compute placement, node groups, is kept symmetric in mechanism between Bridge and Silo; both use the same `node-group` module with no dedicated hardware isolation layer beyond the labeling already used for gVisor targeting, so the measured isolation-depth variable stays scoped to identity, network policy, and subnet/Security-Group boundary, the same three layers already varied locally, rather than also introducing physical compute placement as a fourth, uncontrolled variable specific to the AWS deployment.

## Alternatives Considered

- **Full per-tenant VPCs with no peering, plus a separate shared-services VPC or Transit Gateway for the one deliberately shared component (Ollama)**: considered directly during Phase 6 planning. Rejected given a one-week implementation window with no prior EKS experience; the routing complexity alone, VPC peering or a Transit Gateway, explicit route table management across VPC boundaries, was judged likely to consume the majority of the available time on infrastructure plumbing unrelated to the research questions, with the shared-Ollama exception specifically identified as the piece that would have made this hardest to get right quickly.
- **Dedicated node pools per tenant (physically separate EC2 instances) in addition to the subnet/Security-Group boundary**: considered and rejected for the reason generalized further in ADR-0015's node-group discussion. Adding compute placement as a second, independent isolation mechanism on top of network isolation would have compounded multiple variables into a single "isolation depth" measurement, undermining a clean comparison between Bridge and Silo that holds the mechanism constant and varies only its scope.

## Consequences

**Positive**

- Kept Silo's AWS build achievable within the time available; Silo's actual Terraform apply succeeded with no infrastructure-mechanism failures at all, a direct result of not taking on VPC-peering complexity on top of everything else being built for the first time.
- The isolation-depth variable stays scoped identically to what was already varied locally, keeping the Bridge-versus-Silo comparison's actual independent variable consistent between the local and AWS phases of the evaluation.

**Negative**

- This is a narrower reading of "fully dedicated network per tenant" than AWS's own Pool/Bridge/Silo framing implies, and should be named explicitly as a scoped extension in the paper's Limitations section, not left implicit. A reader familiar with AgentCore's own terminology could otherwise expect literal per-tenant VPC isolation.
- True per-tenant VPC isolation remains untested; whatever latency or cost effect it would add on top of what was actually measured is not captured by this deployment.
