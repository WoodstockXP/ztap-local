#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
TIER1_RUNS="${TIER1_RUNS:-20}"
TIER2_RUNS="${TIER2_RUNS:-5}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
RESULTS_DIR="eval/results/${TIMESTAMP}"
mkdir -p "$RESULTS_DIR"
MANIFEST="$RESULTS_DIR/manifest.csv"
echo "topology,tenant,tier,run,duration_seconds,exit_code,log_file" > "$MANIFEST"
declare -A CONTEXTS=([silo]=kind-ztap [bridge]=kind-ztap-bridge)
declare -A TIER_MODULES=([tier1]=eval.run_gateway_attacks [tier2]=eval.run_agent_attacks)
declare -A TIER_RUNS=([tier1]="$TIER1_RUNS" [tier2]="$TIER2_RUNS")
TOPOLOGIES="${TOPOLOGIES:-silo bridge}"
for topology in $TOPOLOGIES; do
  if ! kubectl config use-context "${CONTEXTS[$topology]}" > /dev/null 2>&1; then
    echo "FATAL: could not switch to context ${CONTEXTS[$topology]} for topology '${topology}'. Is that cluster running? (check: kind get clusters). Aborting rather than silently running these tests against the wrong cluster." >&2
    exit 1
  fi
  echo "=== topology=${topology} confirmed context=$(kubectl config current-context) ==="
  tenant=tenant-a
  for tier in tier1 tier2; do
      module="${TIER_MODULES[$tier]}"
      total_runs="${TIER_RUNS[$tier]}"
      for run in $(seq 1 "$total_runs"); do
        log_file="$RESULTS_DIR/${topology}-${tenant}-${tier}-run${run}.log"
        start=$(date +%s%N)
        kubectl exec deploy/agent-sandbox -n "$tenant" -- python -m "$module" > "$log_file" 2>&1
        exit_code=$?
        end=$(date +%s%N)
        duration=$(awk "BEGIN {printf \"%.3f\", ($end - $start) / 1000000000}")
        echo "${topology},${tenant},${tier},${run},${duration},${exit_code},${log_file}" >> "$MANIFEST"
        echo "[${topology}/${tenant}/${tier} run ${run}/${total_runs}] ${duration}s exit=${exit_code}"
      done
    done
done
echo
echo "Done. Manifest: $MANIFEST"
echo "Analyze with: python eval/analyze_matrix.py $RESULTS_DIR"