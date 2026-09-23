# ADR-0015: Terraform module structure mirrors k8s/ and k8s/bridge/

**Status:** Accepted

## Context

`k8s/` (Silo) and `k8s/bridge/` (Bridge) already share the same application image and differ only in manifests, a structure established before Phase 6 began. Terraform needed an equivalent structure for provisioning AWS infrastructure for both topologies, one that avoids duplicating logic that should stay identical between them (VPC networking, EKS cluster provisioning, node group creation, Cilium installation) while still letting genuinely topology-specific differences (namespace count, per-tenant versus shared identity, subnet-per-tenant versus shared subnet) vary freely.

## Decision

One set of shared, parameterized Terraform modules under `modules/` (`vpc`, `eks-cluster`, `node-group`, `namespaces`, `cilium`, `keycloak`, `gateway`, `ollama`, `observability`, `agent-sandbox`, `network-policy` / `network-policy-silo`, `gvisor`, `ecr`), and one thin root configuration per topology under `envs/` (`envs/bridge`, `envs/silo`) that calls those modules with different variable values. No topology-specific logic lives inside a shared module; every difference between Bridge and Silo is expressed as a variable passed from its own root config.

## Alternatives Considered

- **Two entirely separate Terraform configurations, one per topology, with no shared modules**: rejected. Every fix discovered during Bridge's build, Cilium's masquerade default, the containerd 2.x plugin path, chart version pinning, would have needed to be independently rediscovered and reapplied to a separate Silo configuration, rather than inherited automatically because Silo calls the same, already-fixed module.
- **A single combined root configuration provisioning both topologies from one apply, switched by a variable**: rejected given the account's cost constraint (ADR-0017); the two topologies needed to run sequentially and be torn down between them, not stood up concurrently, which a combined configuration would not naturally support without added complexity for no benefit.

## Consequences

**Positive**

- Every module fix discovered building Bridge, the Helm chart version pins, the Cilium masquerade and interface-naming corrections, the containerd plugin path, applied to Silo automatically, with zero rediscovery cost. Silo's own build had no infrastructure-mechanism failures at all, only two operational mistakes (an image not pushed before a full apply, a transient Spot capacity delay), a direct, measurable benefit of the shared-module structure.
- Keeps the Terraform structure legible against the existing `k8s/` versus `k8s/bridge/` pattern the rest of the project already uses, rather than introducing a second, different organizing principle for the same underlying comparison.

**Negative**

- A module's interface has to anticipate both topologies' needs even when only one of them is built first, and this was not always achieved cleanly on the first attempt. `node-group`'s interface was substantially reworked mid-build once Bridge's real node-pool architecture, sourced from the project's own diagrams, turned out to differ from an earlier, incorrect assumption that node pools could stay symmetric and undifferentiated across topologies.
