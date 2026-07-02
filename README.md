# k8s-shell-simulator

Kubernetes Shell Simulator is a local, browser-based training MVP for hands-on Kubernetes practice. It starts a per-session kind cluster, exposes a Web terminal, shows YAML-defined tasks, and runs checker scripts against the session kubeconfig.

This project is inspired by the workflow of practical Kubernetes exam preparation, but it is an original learning simulator and not a copy of any existing service.

## Architecture

- FastAPI serves the Web UI, REST APIs, and terminal WebSocket.
- xterm.js renders the browser terminal.
- The terminal WebSocket attaches to a PTY running `/bin/bash` inside the simulator container.
- Each session creates an isolated kind cluster named `k8s-sim-{session_id}`.
- Each session writes a separate kubeconfig to `/workspaces/sessions/{session_id}/kubeconfig`.
- The cluster creation script connects the simulator container to Docker's `kind` network and rewrites the kubeconfig API server to `https://{cluster_name}-control-plane:6443`, which keeps kubectl usable from inside the app container when using the host Docker socket.
- Tasks live in `tasks/*.yaml`.
- Checkers live in `checks/*.sh` and run with `KUBECONFIG` set to the session kubeconfig.
- Session progress is stored in `/workspaces/sessions/{session_id}/session.json`.
- A background cleanup worker removes in-memory sessions older than the 2 hour TTL.

## Requirements

- Docker
- Docker Compose v2
- A host environment that can run kind containers

The simulator container mounts the host Docker socket:

```bash
/var/run/docker.sock:/var/run/docker.sock
```

## Start

```bash
docker compose up --build
```

Open:

```text
http://localhost:8000
```

The first page load creates a session and a kind cluster. This can take a minute.

## Usage

Use the browser terminal just like a normal shell:

```bash
kubectl get nodes
kubectl get pods -A
kubectl create namespace exam
```

Select a task and click `Check Answer`.

Task 001:

```bash
kubectl create namespace exam
```

Task 002:

```bash
kubectl -n exam create deployment web --image=nginx:1.25 --replicas=2
```

Task 003:

```bash
kubectl -n exam expose deployment web --name=web-svc --port=80 --target-port=80
```

Click `Reset Environment` to delete and recreate the session cluster.

## Add Tasks

Create a YAML file in `tasks/`:

```yaml
id: "004-example"
title: "Example Task"
difficulty: "easy"
description: |
  Do something with kubectl.
setup:
  manifests: []
check:
  type: "script"
  script: "checks/004-example.sh"
```

The UI lists tasks by `id`.

## Add Checkers

Create an executable script in `checks/`:

```bash
#!/usr/bin/env bash
set -euo pipefail

if kubectl get namespace exam >/dev/null 2>&1; then
  echo "PASS: Namespace exam exists."
  exit 0
else
  echo "FAIL: Namespace exam was not found."
  exit 1
fi
```

Checker scripts receive `KUBECONFIG` for the current session.

## Setup Manifests

Each task can declare setup manifests:

```yaml
setup:
  manifests:
    - manifests/example.yaml
```

The backend includes the helper for applying these manifests with the session kubeconfig. The current MVP keeps the initial tasks empty, but the structure is ready for task-specific setup.
When a task with setup manifests is selected in the UI, the frontend calls `POST /api/sessions/{session_id}/tasks/{task_id}/setup`.

## Build Docker Image

```bash
docker compose build
```

Or directly:

```bash
docker build -t k8s-shell-simulator .
```

## Makefile

```bash
make build
make up
make down
make logs
make clean
```

`make clean` removes the compose volume that stores session files.

## Security Notes

This MVP is for local learning only.

Do not expose it to untrusted users. Do not publish it directly to the internet.

The container mounts the host Docker socket. A user with terminal access in this simulator can effectively control the host Docker daemon.

For production use, add at minimum:

- Authentication and authorization
- Strong session isolation
- Resource limits and quotas
- Network isolation
- Pod Security controls
- Audit logs
- TTL cleanup for all persisted sessions and clusters
- A safer cluster provisioning model that does not expose the host Docker socket to learners

## Troubleshooting

### Session creation fails

Check container logs:

```bash
docker compose logs -f simulator
```

Verify Docker is available on the host:

```bash
docker ps
```

### kind cluster creation times out

Remove old clusters and try again:

```bash
kind get clusters
kind delete cluster --name <cluster-name>
docker compose restart simulator
```

### kubectl cannot connect

In the Web terminal:

```bash
echo $KUBECONFIG
kubectl config current-context
kubectl get nodes
```

### Port 8000 is already used

Change the compose port mapping:

```yaml
ports:
  - "8080:8000"
```

Then open `http://localhost:8080`.
