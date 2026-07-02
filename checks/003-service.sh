#!/usr/bin/env bash
set -euo pipefail

if ! kubectl -n exam get service web-svc >/dev/null 2>&1; then
  echo "FAIL: Service exam/web-svc was not found."
  exit 1
fi

type="$(kubectl -n exam get service web-svc -o jsonpath='{.spec.type}')"
selector="$(kubectl -n exam get service web-svc -o jsonpath='{.spec.selector.app}')"
port="$(kubectl -n exam get service web-svc -o jsonpath='{.spec.ports[0].port}')"
target_port="$(kubectl -n exam get service web-svc -o jsonpath='{.spec.ports[0].targetPort}')"

if [[ "$type" != "ClusterIP" ]]; then
  echo "FAIL: Service web-svc type is '$type', expected 'ClusterIP'."
  exit 1
fi

if [[ "$selector" != "web" ]]; then
  echo "FAIL: Service web-svc selector app is '$selector', expected 'web'."
  exit 1
fi

if [[ "$port" != "80" ]]; then
  echo "FAIL: Service web-svc port is '$port', expected '80'."
  exit 1
fi

if [[ "$target_port" != "80" ]]; then
  echo "FAIL: Service web-svc targetPort is '$target_port', expected '80'."
  exit 1
fi

echo "PASS: Service exam/web-svc is a ClusterIP service on port 80 selecting app=web."
