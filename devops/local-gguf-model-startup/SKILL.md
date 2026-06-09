---
name: local-gguf-model-startup
description: 启动本地 GGUF 模型服务（llama-cpp-python），排查端口占用、模型路径、验证服务
triggers:
  - 启动本地 Qwen 模型
  - ollama/vllm/llama.cpp 模型服务
  - GGUF 文件启动 API 服务
---

# Local GGUF Model Startup with llama-cpp-python

## 核心步骤

### 1. 检查已安装的推理服务
```bash
which ollama lmstudio vllm 2>/dev/null
pip show llama-cpp-python 2>/dev/null
python3 -c "import llama_cpp; print(llama_cpp.__version__)" 2>/dev/null
```

### 2. 查找 GGUF 模型文件
```bash
ls -lh /home/zcxx/models/
find /home/zcxx -name "*.gguf" 2>/dev/null
```

### 3. 检查端口占用（旧服务常占端口）
```bash
lsof -i :11435 2>/dev/null   # 常见 Ollama 端口
lsof -i :8000 2>/dev/null    # vLLM 常用端口
ps aux | grep "llama\|llm\|vllm\|ollama" | grep -v grep
```
**如果端口被占用**：找到 PID → `kill <PID>` → 等待释放

### 4. 安装 llama-cpp-python（如未安装）
```bash
pip install llama-cpp-python[server]
```

### 5. 启动服务
```bash
MODEL_PATH="/home/zcxx/models/Qwen_Qwen3.5-0.8B-Q4_K_M.gguf"
PORT=11435

python3 -m llama_cpp.server \
  --model "$MODEL_PATH" \
  --n_ctx 2048 \
  --n_gpu_layers 0 \
  --host 0.0.0.0 \
  --port $PORT \
  --n_threads 8
```

### 6. 验证
```bash
curl http://localhost:${PORT}/v1/models
curl http://localhost:${PORT}/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "local", "messages": [{"role": "user", "content": "1+1等于几"}]}'
```

## 已知模型文件
| 路径 | 模型 | 大小 | 状态 |
|------|------|------|------|
| `/home/zcxx/models/Qwen_Qwen3.5-0.8B-Q4_K_M.gguf` | Qwen3.5-0.8B | 532MB | ✅ 运行中 |
| `/home/zcxx/models/Qwen3.5-9B-DeepSeek-V4-Flash-Q8_0.gguf` | Qwen3.5-9B DeepSeek | ~9.5GB | ❌ 已停止 |

## 已知端口
- `11435` — 长期被 llama.cpp 服务占用（2026-05-11 ~ 06-05）
- `/tmp/model_cache_35/` — 曾存模型文件，已清理

## 关键教训
1. **先查端口占用**再启动新服务，避免端口冲突
2. **pip install llama-cpp-python[server]** 即可，不需要单独装 llama-server CLI
3. 服务启动后模型 ID 返回 GGUF 文件完整路径，非模型名
4. llama.cpp 有 KV cache bug，超时时重建模型实例
