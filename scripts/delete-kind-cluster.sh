#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="${1:?cluster name is required}"

if kind get clusters | grep -Fxq "$CLUSTER_NAME"; then
  kind delete cluster --name "$CLUSTER_NAME"
fi
