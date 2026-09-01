#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
kind get clusters | grep -qx ztap || kind create cluster --config k8s/kind/kind-ztap.yaml
docker build -t ztap-app:local .
kind load docker-image ztap-app:local --name ztap
kubectl apply -f k8s/base/namespaces/silo-namespaces.yaml
kubectl create configmap ztap-realm-tenant-a --from-file=keycloak/ztap-realm-tenant-a.json -n authorizer-a --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f k8s/base/keycloak/authorizer-a.yaml
kubectl apply -f k8s/base/gateway/enforcer-a.yaml
kubectl rollout status deployment/keycloak -n authorizer-a --timeout=180s
kubectl rollout status deployment/ztap-gateway -n enforcer-a --timeout=60s
echo "tenant-a stack up: keycloak.authorizer-a, ztap-gateway.enforcer-a"
