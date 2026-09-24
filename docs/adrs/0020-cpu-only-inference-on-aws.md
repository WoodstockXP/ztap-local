# ADR-0020: CPU-only inference on AWS, GPU quota request denied

**Status:** Accepted

## Context

The project's own architecture diagram (`final_cloudagnostic_diagrams.pdf`) names a GPU instance (T4 or L4) for the `inference` node pool. A Service Quota increase request for `Running On-Demand G and VT instances`, needed to launch any GPU instance type at all, was submitted early in the AWS build and denied outright, with no path to appeal offered beyond reopening the case with a more detailed use case. Separately, neither `ollama.yaml` (the manifest `ollama`'s module ports directly) nor the local deployment it mirrors has ever included GPU wiring: no NVIDIA device plugin, no `resources.limits` entry for `nvidia.com/gpu`, no GPU-enabled node AMI. Locally, this was never a gap, the development machine's GPU is used directly by Ollama outside Kubernetes; on AWS, actually using a GPU instance's GPU would have required adding all three of these pieces from scratch, independent of whether the quota request had been approved.

## Decision

`inference` runs on plain `t3.xlarge`, the same instance type used for every other node pool, not a GPU instance. This was decided even before the quota denial was confirmed: `g4dn.xlarge` was the original value in the node pool configuration, and was changed specifically because nothing in the stack was wired to use its GPU regardless of whether the instance launched successfully.

## Alternatives Considered

- **Appeal the quota denial and add GPU wiring** (NVIDIA device plugin, GPU-enabled node AMI, `resources.limits`): rejected. Even a successful appeal would only unlock a GPU instance that still needed all of this work to actually benefit from it, and this was weighed against the same one-week timeline pressure that shaped every other infrastructure decision this phase (see ADR-0014's Negative section). The marginal benefit, faster Tier 2 inference, did not justify the added complexity and a second dependency on AWS approving something once already denied.
- **Launch `g4dn.xlarge` anyway, running Ollama on its CPU rather than its GPU**: rejected as simply paying for GPU capacity nothing would use, a real cost with no corresponding benefit, especially notable given the account's credit balance was already a live constraint (ADR-0017).

## Consequences

**Positive**

- Removed GPU instance quota entirely as a dependency for finishing the deployment; `inference`'s node group has never been blocked by an account restriction, unlike every other node pool at various points this phase.
- Kept `ollama`'s Terraform module a direct, unmodified port of the existing `ollama.yaml`, no new GPU-specific resources or values to build, test, or explain.

**Negative**

- Tier 2 evaluation runs are CPU-bound inference throughout, on both AWS topologies and locally. Any duration or throughput numbers reported are not representative of what a GPU-backed deployment would show; this should be named explicitly wherever Tier 2 timing is discussed; it is not a like-for-like comparison against a production deployment that would reasonably use GPU inference.
- The project's own diagram names a GPU instance for this pool. This ADR is the record of why the actual deployment diverges from that diagram, worth citing directly if the diagram is included in the paper without a caption noting the divergence.
