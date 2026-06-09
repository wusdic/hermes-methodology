---
name: hermes-docker-backend-trap-recovery
description: Recover Hermes Agent when terminal.backend is set to docker but Docker is not installed — all tools fail with "Docker executable not found"
---

# Hermes Docker Backend Trap — Recovery Procedure

## Problem
When `terminal.backend` is set to `docker` but Docker is not installed, **ALL tools fail** with:
```
RuntimeError: Docker executable not found in PATH or known install locations.
```
This includes tools that seem like they should work locally: `terminal`, `execute_code`, `search_files`, `read_file`, `patch`, `write_file`.

The trap: You cannot use file tools to fix the config, because they all route through the Docker-checked terminal environment.

## Two Distinct Failure Modes

### Mode A: Docker not installed (original skill)
- Error: `RuntimeError: Docker executable not found`
- `hermes config set` CLI still works → easy recovery

### Mode B: Docker installed but image pull fails (today's case)
- Docker daemon running (`docker ps` works)
- But image (e.g. `nikolaik/python-nodejs:python3.11-nodejs20`) can't be pulled → network blocked
- Error: `docker run ... returned non-zero exit status 125`
- **All tools fail including `hermes config set`** → CLI itself tries to start a docker container
- **Only browser/send_message/cronjob tools survive** (bypass Docker backend check)
- `execute_code` also routes through Docker → also fails with same error
- Recovery: user must manually run `hermes config set terminal.backend local` on the server

**Critical detection**: When ALL tools fail with the same Docker "exit status 125" traceback — not "not found" — it means Docker IS installed but the backend image is unreachable. This is Mode B, not Mode A.

## Symptoms
- `hermes config show` shows `Backend: docker`
- All tool calls fail with Docker "exit status 125" or "not found"
- `hermes config set terminal.backend local` also fails (CLI itself blocked)
- `send_message` still works
- Browser tools still work

## Recovery Steps

### Step 1: Verify the problem
Check if config still shows docker:
```bash
hermes config show | grep -A5 "Terminal"
```
Expected: `Backend: docker`

### Step 2: Fix via CLI (only way out)
```bash
hermes config set terminal.backend local
```
> Note: `sed -i 's/backend: "docker"/backend: "local"/' ~/.hermes/config.yaml` does NOT work reliably because the running Hermes process has cached the config in memory.

### Step 3: Verify fix
```bash
hermes config show | grep -A5 "Terminal"
```
Expected: `Backend: local`

### Step 4: If hermes CLI also fails (Mode B — image pull fails)
If even `hermes config set` is blocked (Docker error on the hermes command itself), the user must manually run on the server:
```bash
hermes config set terminal.backend local
```
This is the only reliable way because the running Hermes agent process does not reload config from disk.

**Why this happens**: When `terminal.backend=docker`, the hermes CLI itself tries to start a Docker container on each command. If the image isn't available, the CLI fails before it can even parse the `config set` argument.

### Step 5: Restart Hermes process (if needed)
If tools still fail after config change, the Hermes agent process needs restart:
```bash
# Find the running process
ps aux | grep hermes | grep -v grep

# If using systemd
sudo systemctl restart hermes
```

## Prevention
Before setting `terminal.backend docker`, always verify Docker is installed AND image is pullable:
```bash
docker --version
docker pull nikolaik/python-nodejs:python3.11-nodejs20  # test image pull
```

If Docker Hub is blocked (China network), configure a mirror before setting backend:
```bash
# Option 1: daocloud mirror (already tried)
sudo mkdir -p /etc/docker
echo '{"registry-mirrors": ["https://docker.m.daocloud.io"]}' | sudo tee /etc/docker/daemon.json
sudo systemctl restart docker  # requires systemd/sudo

# Option 2: aliyun mirror (if account available)
# Option 3: pull images manually before enabling docker backend
docker pull python:3.11-slim  # lighter alternative
```

## Key Insight
The Docker backend check happens at environment initialization time in `hermes-agent/tools/terminal_tool.py`. All tools (including file tools) go through this check because they run commands in the terminal environment. Only `send_message` and browser tools bypass this check in some configurations.
