#!/usr/bin/env bash
set -euo pipefail

KUBECTL_VERSION="${KUBECTL_VERSION:-v1.30.2}"
KIND_VERSION="${KIND_VERSION:-v0.23.0}"
TARGET_ARCH="$(dpkg --print-architecture)"

case "$TARGET_ARCH" in
  amd64) GO_ARCH="amd64" ;;
  arm64) GO_ARCH="arm64" ;;
  *) echo "Unsupported architecture: $TARGET_ARCH" >&2; exit 1 ;;
esac

apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  gnupg \
  lsb-release \
  bash \
  jq \
  vim \
  tmux

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=${TARGET_ARCH} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update
apt-get install -y --no-install-recommends docker-ce-cli

curl -fsSLo /usr/local/bin/kubectl "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${GO_ARCH}/kubectl"
chmod +x /usr/local/bin/kubectl

curl -fsSLo /usr/local/bin/kind "https://kind.sigs.k8s.io/dl/${KIND_VERSION}/kind-linux-${GO_ARCH}"
chmod +x /usr/local/bin/kind

rm -rf /var/lib/apt/lists/*
