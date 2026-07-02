#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="${1:?cluster name is required}"
KUBECONFIG_PATH="${2:?kubeconfig path is required}"

mkdir -p "$(dirname "$KUBECONFIG_PATH")"

if kind get clusters | grep -Fxq "$CLUSTER_NAME"; then
  kind delete cluster --name "$CLUSTER_NAME"
fi

kind create cluster --name "$CLUSTER_NAME" --kubeconfig "$KUBECONFIG_PATH" --wait 120s
chmod 0600 "$KUBECONFIG_PATH"

if docker network inspect kind >/dev/null 2>&1; then
  docker network connect kind "$(hostname)" >/dev/null 2>&1 || true
  kubectl --kubeconfig "$KUBECONFIG_PATH" config set-cluster "kind-${CLUSTER_NAME}" \
    --server="https://${CLUSTER_NAME}-control-plane:6443" >/dev/null
fi

kubectl --kubeconfig "$KUBECONFIG_PATH" wait --for=condition=Ready nodes --all --timeout=120s
