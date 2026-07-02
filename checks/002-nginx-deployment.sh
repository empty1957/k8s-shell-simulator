#!/usr/bin/env bash
set -euo pipefail

if ! kubectl -n exam get deployment web >/dev/null 2>&1; then
  echo "FAIL: Deployment exam/web was not found."
  exit 1
fi

image="$(kubectl -n exam get deployment web -o jsonpath='{.spec.template.spec.containers[0].image}')"
replicas="$(kubectl -n exam get deployment web -o jsonpath='{.spec.replicas}')"

if [[ "$image" != "nginx:1.25" ]]; then
  echo "FAIL: Deployment web image is '$image', expected 'nginx:1.25'."
  exit 1
fi

if [[ "$replicas" != "2" ]]; then
  echo "FAIL: Deployment web replicas is '$replicas', expected '2'."
  exit 1
fi

echo "PASS: Deployment exam/web uses nginx:1.25 with 2 replicas."
