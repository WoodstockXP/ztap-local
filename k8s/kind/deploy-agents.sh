#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
kubectl apply -f k8s/base/inference/ollama.yaml
docker build -t ztap-app:local .
kind load docker-image ztap-app:local --name ztap
kubectl apply -f k8s/base/agent/agent-sandbox-a.yaml
kubectl apply -f k8s/base/agent/agent-sandbox-b.yaml
kubectl rollout status deployment/agent-sandbox -n tenant-a --timeout=60s
kubectl rollout status deployment/agent-sandbox -n tenant-b --timeout=60s
echo "agent sandboxes up: tenant-a, tenant-b."
echo "ollama is pulling llama3.2:3b in the background (a few GB, this can take a while); the pod won't report Ready until that finishes, check with:"
echo "  kubectl get pods -n inference"
echo "  kubectl exec -n inference deploy/ollama -- ollama list"
