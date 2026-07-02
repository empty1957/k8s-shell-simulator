#!/usr/bin/env bash
set -euo pipefail

if kubectl get namespace exam >/dev/null 2>&1; then
  echo "PASS: Namespace exam exists."
  exit 0
else
  echo "FAIL: Namespace exam was not found."
  exit 1
fi
