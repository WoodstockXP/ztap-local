# ADR-0019: Observability (Prometheus, Grafana, OpenTelemetry) not deployed on AWS

**Status:** Accepted (documented limitation)

## Context

Locally, and per the project's Monitoring pillar, a telemetry layer, Hubble via Cilium plus a Prometheus/Grafana/OTel stack, is intended runtime observability infrastructure, not itself part of the security architecture being evaluated. On AWS, this has no local manifest equivalent to port from; it is new infrastructure, built directly via the `kube-prometheus-stack` and OpenTelemetry Collector Helm charts. Hubble itself is already running, enabled directly in the `cilium` module's Helm values, and is unaffected by what follows.

## Decision

The `observability` module (`kube-prometheus-stack`, OpenTelemetry Collector) is included in the Terraform codebase and can be applied, but is deliberately left out of both topologies' actual deployed, verified state for this evaluation. Its pre-install admission webhook job (`kube-prometheus-stack-admission-create`) fails with `BackoffLimitExceeded`, root-caused directly, not left as a guess, to pods being unable to reach the Kubernetes API server's ClusterIP (`172.20.0.1:443`) at all. `kube-proxy` was independently confirmed healthy on every node, ruling it out as the cause. The leading, unconfirmed theory: Cilium's masquerade rule, enabled to fix Ollama's internet egress and documented in `terraform/README.md`'s Known Errors, decides what to masquerade based on whether traffic is leaving the VPC CIDR (`10.0.0.0/16`); the Kubernetes Service CIDR (`172.20.0.0/16`) was never part of that range, so Service-destined traffic is plausibly masqueraded by mistake, a packet meant for `kube-proxy`'s local `iptables` interception instead sent out as though leaving the cluster.

## Alternatives Considered

- **Setting `kubeProxyReplacement: true` in the `cilium` module**, letting Cilium own Service routing entirely via its own eBPF datapath instead of coexisting with `kube-proxy`'s `iptables` rules: identified as the likely correct fix, not attempted. This is a cluster-wide Service-routing change, not a scoped one, and typically also requires deleting the `kube-proxy` DaemonSet entirely and explicitly configuring `k8sServiceHost`/`k8sServicePort` so Cilium can bootstrap its own connection to the API server before its eBPF datapath is even up. Given both topologies were already fully built, deployed, and verified, and a real evaluation dataset already collected, attempting an invasive, cluster-wide networking change this close to the deadline was judged not worth the risk of breaking already-working infrastructure, the same reasoning that ended the second gVisor attempt (ADR-0018).
- **Excluding only the Service CIDR from Cilium's masquerade range**, rather than switching to full `kube-proxy` replacement: a narrower, less invasive alternative fix worth trying first if this is revisited. Not attempted within this timeline; recorded here specifically so it is tried before the more invasive `kubeProxyReplacement` change next time.

## Consequences

**Positive**

- Scoped precisely: Keycloak, the gateway, Ollama, and the agent sandbox never call the Kubernetes API directly, only Prometheus and `kube-state-metrics` do, to discover and watch other pods, so this gap does not affect any result in the evaluation dataset. Hubble, the CNI-level observability already relied on throughout this project's debugging, is unaffected and running normally.
- The root cause is genuinely diagnosed, not just "it timed out and we moved on." A specific, falsifiable hypothesis (Service CIDR masquerade) and a specific untried fix are both on record, making this cheap to pick back up.

**Negative**

- No dashboard-level runtime metrics (request rates, resource utilization over time) were collected for either topology on AWS. The eval matrix's own `manifest.csv` (duration, exit code per run) is the actual data source for this evaluation's timing claims and does not depend on this gap, but any future work wanting continuous operational visibility into the AWS deployment needs this resolved first.
