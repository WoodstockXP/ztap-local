# Setting up and running the eval harness

This is the complete path from a clean machine to real, comparable test results for both Silo and Bridge. Read this top to bottom the first time; after that, the two bootstrap scripts and `run_matrix.sh` are all you need.

## 0. One-time host setup

Kubernetes-in-Docker needs more `inotify` watches than most Linux systems ship with by default. Without this, cluster creation fails in confusing ways (`kube-proxy` and other pods crash-loop with `too many open files`). Do this once, before anything else:

```bash
sudo sysctl -w fs.inotify.max_user_watches=524288
sudo sysctl -w fs.inotify.max_user_instances=512
echo 'fs.inotify.max_user_watches=524288' | sudo tee /etc/sysctl.d/99-ztap-inotify.conf
echo 'fs.inotify.max_user_instances=512' | sudo tee -a /etc/sysctl.d/99-ztap-inotify.conf
sudo sysctl --system > /dev/null
```

This should survive reboots. If you ever see `too many open files` again, check `sysctl fs.inotify.max_user_watches` first, if it's back down at `65536`, this didn't persist for some reason and needs redoing.

## 1. The one hard constraint: only one cluster at a time

Silo is 5 kind nodes, Bridge is 6, and Bridge's Ollama holds a multi-gigabyte model in memory the whole time it's up. On a 16GB machine, running both at once is not reliable, it has already caused a cluster creation to fail outright from memory pressure. **Always tear one down before bringing the other up.** Check what's currently running with `kind get clusters`.

## 2. Standing up Silo

```bash
chmod +x k8s/kind/bootstrap-silo.sh
k8s/kind/bootstrap-silo.sh
```

This one script does everything: builds the gVisor-enabled node image if it doesn't already exist, creates the cluster, installs Cilium, deploys both tenants (Keycloak, gateway), applies every NetworkPolicy, applies the gVisor `RuntimeClass`, then deploys Ollama and both agent sandboxes. It's safe to rerun if something fails partway. Expect the very first run on a machine to take a while, pulling the gVisor binaries, the Cilium images, and the `qwen2.5:7b` model (several gigabytes) all happen here.

If you want to understand *why* each piece is there, or see specific guarantees (the Keycloak issuer-mismatch bug, isolation with vs without NetworkPolicy, gVisor actually intercepting syscalls) demonstrated directly, walk through `k8s/README.md`'s numbered steps instead. That doc is for learning and verifying, this section is for getting back to a working state quickly.

## 3. Standing up Bridge

```bash
kind delete cluster --name ztap
chmod +x k8s/bridge/kind/bootstrap-bridge.sh
k8s/bridge/kind/bootstrap-bridge.sh
```

Same idea, one script, everything included. `k8s/bridge/README.md` is the equivalent learning/verification doc if you want the walkthrough.

## 4. Running a single test manually

Useful for spot-checks and debugging. Both tiers read `ZTAP_KEYCLOAK_TOKEN_URL`, `ZTAP_GATEWAY_URL`, and `ZTAP_OLLAMA_BASE_URL` the same way `agent/run_agent.py` does, and every `agent-sandbox` pod already has these set correctly, no overrides needed:

```bash
kubectl exec -it deploy/agent-sandbox -n tenant-a -- python -m eval.run_gateway_attacks
kubectl exec -it deploy/agent-sandbox -n tenant-a -- python -m eval.run_agent_attacks
```

Add `--only T2-G4-02` (or any comma-separated case IDs) to the second command to run a subset while iterating.

**Always use `tenant-a`, on both Silo and Bridge.** Every test case is hardcoded to authenticate as `alice`. On Silo, `alice` only exists in tenant-a's own Keycloak realm, running from tenant-b's pod fails immediately with a Keycloak `invalid_grant` error. This isn't a bug to fix, Silo's two tenants are deliberately mirrored infrastructure, so `alice attacking tenant-b's records via tenant-a's gateway` (already covered by the corpus's own cross-tenant cases) is sufficient evidence the reverse direction would be stopped the same way.

To switch which cluster you're talking to: `kubectl config use-context kind-ztap` (Silo) or `kind-ztap-bridge` (Bridge).

## 5. Running the full comparison (the actual deliverable)

This is what Phase 5's milestone is asking for: repeated, timed, comparable runs across both topologies.

```bash
TOPOLOGIES=silo TIER1_RUNS=10 TIER2_RUNS=2 eval/run_matrix.sh
python eval/analyze_matrix.py eval/results/<the-timestamp-it-printed>
```

Then tear Silo down, bring Bridge up (section 3), and run the same thing with `TOPOLOGIES=bridge`. Each invocation writes its own timestamped results directory under `eval/results/`, nothing gets overwritten.

`TIER1_RUNS`/`TIER2_RUNS` default to `20`/`5` if you don't set them. Tier 1 has no LLM involved and is fast, run it as many times as you like. Tier 2 makes real model calls and is slow (and, on this machine, has previously come close to overloading it), start small (`TIER2_RUNS=2`) and raise it once you know how long a batch actually takes.

`analyze_matrix.py`'s output has three parts:
- **Duration summary**: mean/min/max wall-clock time per tier. A Tier 2 run that's dramatically faster than the others usually means it crashed rather than actually ran, cross-check against the next section.
- **Crashed runs**: any run with a nonzero exit code. Should be empty. If it isn't, go read that specific log file before trusting anything else from that batch.
- **Inconsistent test case outcomes**: any test case that didn't produce the same result on every repeated run. For Tier 1 this should always be empty, it's deterministic. For Tier 2 it's genuinely interesting, real evidence about how reliable the model's behavior is, not a bug to chase.

## 6. Comparing the two results directories

Once you have one clean directory each for Silo and Bridge, that's the actual dataset, run `analyze_matrix.py` on each and compare the reports by eye (or write a small script later that diffs them, once you know what shape the comparison needs to take for the paper).