#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
kind get clusters | grep -qx ztap || kind create cluster --config k8s/kind/kind-ztap.yaml
docker build -t ztap-app:local .
kind load docker-image ztap-app:local --name ztap
kubectl apply -f k8s/base/namespaces/silo-namespaces.yaml
kubectl create configmap ztap-realm-tenant-b --from-file=keycloak/ztap-realm-tenant-b.json -n authorizer-b --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f k8s/base/keycloak/authorizer-b.yaml
kubectl apply -f k8s/base/gateway/enforcer-b.yaml
kubectl rollout status deployment/keycloak -n authorizer-b --timeout=180s
kubectl rollout status deployment/ztap-gateway -n enforcer-b --timeout=60s
echo "tenant-b stack up: keycloak.authorizer-b, ztap-gateway.enforcer-b"
