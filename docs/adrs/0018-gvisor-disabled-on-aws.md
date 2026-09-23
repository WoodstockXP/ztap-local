# ADR-0018: gVisor sandboxing disabled on the AWS deployment

**Status:** Accepted (documented limitation)

## Context

Locally, `agent-sandbox` pods in both topologies run under the `gvisor` RuntimeClass, giving genuine kernel-level sandboxing on top of Kubernetes' namespace and network isolation, achieved by baking the `runsc` and `containerd-shim-runsc-v1` binaries directly into the kind node's container image before the cluster exists (`gvisor-node.Dockerfile`). EKS managed node groups have no equivalent mechanism without building and maintaining a custom AMI, a substantially larger undertaking than the implementation window allowed. Two alternative install mechanisms were attempted and both failed for specific, diagnosed reasons, not abandoned for lack of trying.

## Decision

`agent-sandbox`'s `gvisor_enabled` variable defaults to `false` in both topologies on AWS; pods run under the standard `runc` runtime. The `gvisor` `RuntimeClass` definition itself (`modules/gvisor/main.tf`, `handler = runsc`) is confirmed correct and left in place, and the variable exists specifically so re-enabling it later, once a working install mechanism exists, is a one-line change per module call, not a rewrite.

## Alternatives Considered

- **A privileged DaemonSet patching already-running nodes** (`hostPath` chroot into the node's real filesystem, edit `containerd`'s config, `systemctl restart containerd`): the first approach tried. Two distinct sub-issues were found and fixed along the way: missing `mount_propagation` on the `hostPath` volume, meaning the container couldn't see the host's live `/run` mount needed for `systemctl` to reach `containerd`'s real D-Bus socket, and `containerd` 2.x's CRI plugin config path changing from `io.containerd.grpc.v1.cri` to `io.containerd.cri.v1.runtime`, undocumented in most currently available AWS/gVisor tutorials, which predate this `containerd` version. Even after both were corrected and independently confirmed, the binary present, the config file correct, `containerd` genuinely restarted, the runtime registration still never took effect. The underlying `containerd` `imports` drop-in mechanism used for the fix did not behave the way `containerd`'s own `config dump` output claimed it would, and the exact reason was not conclusively identified before time ran out on this approach.
- **A boot-time install via a custom `aws_launch_template` `user_data` script**, installing before `containerd`'s first-ever start rather than patching a running instance: the second approach tried, motivated by removing the live-restart uncertainty entirely. The gVisor binaries installed correctly this way, after also discovering gVisor's release artifact format itself had changed, from individually downloadable `runsc` and `containerd-shim-runsc-v1` files to a single tarball, breaking the URLs the first approach had used successfully only hours earlier. However, appending directly to `containerd`'s base `config.toml` before `nodeadm` had generated it appears to have interfered with `nodeadm`'s own AL2023 bootstrap sequence, causing `NodeCreationFailure` on both tenant node groups, a materially worse failure mode than the first approach, since it broke node bootstrap entirely rather than merely failing to enable gVisor. This is what ended the line of investigation: the risk profile changed from wasting time to breaking already-working infrastructure, which was judged not worth the trade against the remaining time.

## Consequences

**Positive**

- Neither failed attempt left the cluster in a broken state once each was rolled back; `agent-sandbox` on plain `runc` has been verified working end-to-end on both topologies via a real, model-driven agent request, not a hand-constructed test, including the correct cross-tenant Cedar denial.
- Leaving the `RuntimeClass` and the `gvisor_enabled` variable in place, rather than removing them, means this is recoverable infrastructure debt, not a design dead end.

**Negative**

- The AWS deployment's actual runtime isolation is one layer shallower than the local deployment's for the duration this remains unresolved: standard container namespace isolation (`runc`) rather than gVisor's additional kernel-interface-level sandboxing. Any claim in the paper about kernel-level agent sandboxing must be scoped explicitly to the local evaluation, not implied to also hold for the AWS numbers, until this is resolved.
- Two distinct, real `containerd`/AL2023 platform quirks were found and are documented here and in `terraform/README.md`'s Known Errors section, the plugin path change, the `nodeadm` bootstrap interference, but the actual root cause of the drop-in import failure specifically was not conclusively identified. Revisiting this should start from direct evidence, `containerd`'s own startup journal, not just `config dump`, before attempting a third install mechanism.
