#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
./deploy-tenant-a.sh
./deploy-tenant-b.sh
kubectl apply -f ../base/network-policy/default-deny-all.yaml
kubectl apply -f ../base/network-policy/allow-dns.yaml
kubectl apply -f ../base/network-policy/allow-enforcer-authorizer.yaml