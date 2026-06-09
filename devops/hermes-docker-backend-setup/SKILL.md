---
name: hermes-docker-backend-setup
description: Hermes Agent v0.15.1 Docker backend setup on China-networked Linux — binary install, mirror config, socket permissions, and critical discoveries about spawn/delegate_task
tags: [docker, hermes, china-network, setup]
created: 2026-06-04
---

# Hermes Agent Docker Backend Setup (China Network)

## Context
Hermes Agent v0.15.1 with Docker backend on a China-networked Linux VM. Docker Hub is inaccessible, requiring domestic mirror configuration.

## Situation
- Hermes Agent upgraded from 0.11.0 → 0.15.1
- `hermes config set terminal.backend docker` works
- But Docker Hub (`registry.hub.docker.com`) is blocked in China
- Container image pull fails without mirror registry

## Solution: Manual Binary Install + Mirror Config

### 1. Download Docker Binary (No apt)
```bash
# Download from Aliyun mirror (domestic)
mkdir -p /tmp/docker-install
cd /tmp/docker-install
curl -L "https://mirrors.aliyun.com/docker-ce/linux/static/stable/x86_64/docker-26.1.0.tgz" -o docker.tgz
tar xzf docker.tgz
cp docker/* ~/bin/
chmod +x ~/bin/dockerd ~/bin/docker
```

### 2. Start dockerd Manually
```bash
sudo -S ~/bin/dockerd &  # Use full path, background
```

### 3. Fix Socket Permissions
```bash
sudo groupadd docker 2>/dev/null || true
sudo usermod -aG docker $USER
sudo chmod 666 /var/run/docker.sock
# Log out and back in for group membership, or use newgrp
```

### 4. Configure Registry Mirror (Critical for China)
```bash
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json <<'EOF'
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.xuanyuan.me"
  ]
}
EOF
sudo pkill dockerd; sudo ~/bin/dockerd &
```

### 5. Configure Hermes to Use Docker Backend
```bash
hermes config set terminal.backend docker
# Optional: set custom image
hermes config set terminal.image nikolaik/python-nodejs:python3.11-nodejs20
```

### 6. Verify
```bash
docker images  # Should list images
hermes config show | grep backend
```

## Key Discoveries (Trial & Error)

### hermes spawn Does NOT Exist
The documentation mentions `hermes spawn` CLI but it doesn't exist in v0.15.1. The actual parallelism mechanism is the built-in `delegate_task` tool.

### delegate_task Limits
- `max_concurrent_children`: default 3 (controls parallelism level)
- `max_spawn_depth`: default 1 (扁平, no nested agents by default)
- To enable nested agents: set `delegation.max_spawn_depth >= 2` in config

### Docker Image Pre-pull
Since Docker Hub is blocked, pre-pull the image before heavy usage:
```bash
docker pull nikolaik/python-nodejs:python3.11-nodejs20
```

### Docker Backend vs Local
When Docker is not installed/running, all terminal tools hang indefinitely. Recovery:
```bash
hermes config set terminal.backend local
```

## Troubleshooting

### dockerd Won't Start
```bash
# Check if port 2375 is already bound
sudo netstat -tlnp | grep 2375
# Or check logs
sudo ~/bin/dockerd --debug 2>&1 | tail -20
```

### Socket Permission Denied Even After chmod
```bash
# May need to re-login for group membership
newgrp docker
# Or run docker commands with sudo temporarily
```

### Hermes Docker Backend Hangs
1. Check Docker is running: `docker info`
2. Check image exists: `docker images`
3. Fall back: `hermes config set terminal.backend local`

## Related
- Skill: `hermes-docker-backend-trap-recovery` (exists, covers recovery not setup)
