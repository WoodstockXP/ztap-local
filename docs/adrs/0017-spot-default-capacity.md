# ADR-0017: Spot instances as the default node capacity type on AWS

**Status:** Accepted

## Context

The AWS account available for Phase 6 is a personal account carrying $120 in promotional credit, and turned out to be on AWS's "Free Plan," a distinct, account-wide restriction, separate from the older per-service Free Tier, blocking On-Demand instances above Free Tier eligible types entirely. This was discovered only when the first `aws_eks_node_group` creation failed with an explicit `InvalidParameterCombination` error citing Free Tier eligibility. A subsequent Service Quota increase request for GPU instances (`Running On-Demand G and VT instances`) was denied outright, and an AWS Support case confirmed the restriction was account-plan based, self-service upgradeable via Billing, not something Support could waive directly.

## Decision

`node_capacity_type` defaults to `SPOT` in both `envs/bridge/variables.tf` and `envs/silo/variables.tf`, rather than the more conventional `ON_DEMAND` default, because Spot capacity was confirmed empirically not to be subject to the same Free Plan restriction that blocked On-Demand `t3.xlarge` launches.

## Alternatives Considered

- **Upgrading the account to AWS's paid plan**: the more correct long-term fix, left as an open action item rather than pursued mid-build, since finishing the deployment mattered more under the timeline than resolving the account's billing tier immediately. Should be revisited before any evaluation run where Spot's two-minute reclamation notice would risk interrupting a long-running data collection pass.
- **A separate or institutional AWS account (MITACS, TRU research computing)**: raised directly once the credit balance was nearly exhausted mid-build. Not pursued within Phase 6's timeline; worth requesting going forward given the personal account's credit balance is not sustainable for continued work at this scale.

## Consequences

**Positive**

- Unblocked node group creation entirely without requiring account-plan approval or a support ticket resolution, both of which were either denied or left pending, keeping the build moving within the available time.
- Cost-neutral to favorable relative to On-Demand pricing, relevant given the account's own near-zero-credit scare partway through Bridge's build.

**Negative**

- Every node in both topologies, including the ones hosting Keycloak, the gateway, and Ollama, not only tenant compute, is subject to two-minute-notice reclamation for the duration of this deployment. This was accepted as a working-session risk rather than mitigated (no checkpointing, no reclamation handling), and is a real limitation for any evaluation run intended to be uninterrupted; the eval matrix runs completed for this evaluation happened not to be interrupted, but that was not guaranteed in advance.
- The account's Free Plan status is a personal-account artifact, not a property of AWS EKS or the Bridge/Silo architecture, and should not be read back into the paper as though it were a finding about cloud deployment cost or complexity in general.
