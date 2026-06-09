---
name: sudo-subprocess-automation
description: sudo 管道密码在非交互 shell 中失败——使用 subprocess.Popen + communicate() 正确传递密码；Ubuntu Docker 包名为 docker.io 而非 docker-ce
tags: [sudo, subprocess, python, docker, ubuntu]
---

# sudo Subprocess 自动化

## 触发条件

在非交互式 shell（Hermes Agent terminal）中，`echo 'password' | sudo -S cmd` 失败：

```
sudo: a terminal is required to read the password
sudo: no password was provided
```

## 根因

shell 管道方式 `echo X | sudo -S` 在当前环境不工作，必须用 Python `subprocess` 的 `communicate()`。

## 正确做法

```python
import subprocess

def run(cmd):
    p = subprocess.Popen(['sudo', '-S'] + cmd.split(),
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = p.communicate('sdzc@8080\n', timeout=60)
    print(out)
    if err: print('ERR:', err)
```

`communicate()` 正确将密码附加到 stdin，比 shell pipe 可靠得多。

## 本系统关键信息

| 项目 | 值 |
|------|-----|
| sudo 密码 | `sdzc@8080` |
| 发行版 | Ubuntu 24.04 |
| Docker 包名 | `docker.io`（不是 `docker-ce`） |
| Docker 卸载命令 | `apt remove --purge -y docker.io containerd` |
| 数据目录清理 | `rm -rf /var/lib/docker /var/lib/containerd` |
| 用户组清理 | `groupdel docker` |

## 完整 Docker 卸载流程

```python
import subprocess, time

def run(cmd):
    p = subprocess.Popen(['sudo', '-S'] + cmd.split(),
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = p.communicate('sdzc@8080\n', timeout=120)
    print(out)

run('systemctl stop docker docker.socket containerd')
time.sleep(1)
run('apt remove --purge -y docker.io containerd')
run('rm -rf /var/lib/docker /var/lib/containerd /var/run/docker.sock')
run('groupdel docker')
run('apt autoremove -y')  # 清理自动安装的依赖
```

## 验证清理

```bash
which docker          # 应返回空
docker --version      # 应报错
ls /var/lib/docker    # 应报错：没有那个文件或目录
getent group docker   # 应返回空
```
