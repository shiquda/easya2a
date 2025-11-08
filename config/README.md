# 配置文件说明

## 快速开始

1. **复制示例配置文件**：
   ```bash
   cp agents.example.yaml agents.yaml
   ```

2. **配置环境变量**：
   ```bash
   # Windows
   set OPENAI_API_KEY=your-api-key-here

   # Linux/Mac
   export OPENAI_API_KEY=your-api-key-here
   ```

3. **编辑配置文件**：
   根据需要修改 `agents.yaml`，调整LLM provider配置和Agent设置。

## 安全提示

⚠️ **重要**：
- `agents.yaml` 包含在 `.gitignore` 中，**不会被提交到git**
- 切勿在示例文件中硬编码真实的API密钥
- 使用环境变量 `${VAR_NAME}` 格式引用敏感信息

## 配置文件结构

### agents.example.yaml
- 示例配置文件，包含详细注释
- 可安全提交到git仓库
- 作为新用户的起始模板

### agents.yaml
- 实际使用的配置文件
- 由用户从example复制并修改
- 包含真实的API密钥和自定义配置
- **已被.gitignore忽略，不会被提交**

## base_url 配置说明

`base_url` 字段支持使用OpenAI兼容的API服务：

### 默认OpenAI（可省略或设为null）
```yaml
base_url: null  # 使用默认 https://api.openai.com/v1
```

### Azure OpenAI
```yaml
base_url: "https://your-resource.openai.azure.com"
api_key: "${AZURE_OPENAI_KEY}"
model: "your-deployment-name"  # Azure使用deployment名称
```

### 本地Ollama
```yaml
base_url: "http://localhost:11434/v1"
api_key: "dummy"  # Ollama不需要真实密钥
model: "llama2"
```

### 其他OpenAI兼容服务
任何实现OpenAI API规范的服务都可以通过设置 `base_url` 使用。

## Agent URL 配置

每个Agent可以配置自定义的URL，这在以下场景很有用：

### 本地开发（默认）
```yaml
# 不设置url字段，自动使用 http://localhost:{port}
agents:
  - name: my-agent
    port: 9001
    # url会自动生成为 http://localhost:9001
```

### 端口转发 / 反向代理
```yaml
agents:
  - name: my-agent
    port: 9001
    url: "https://example.com/agents/my-agent/"
```

### ngrok等隧道服务
```yaml
agents:
  - name: my-agent
    port: 9001
    url: "https://abc123.ngrok.io"
```

### 云端Notebook（如你的场景）
```yaml
agents:
  - name: my-agent
    port: 9001
    url: "https://nat-notebook.example.com/ws-xxx/proxy/9001/"
```

**提示**:
- URL应该是完整的可访问地址
- 确保URL末尾的斜杠与实际部署一致
- 修改URL后需要重启服务器

## 常见问题

**Q: 为什么没有 agents.yaml 文件？**
A: 这是正常的。首次使用时需要从 `agents.example.yaml` 复制创建。

**Q: 修改了配置后如何生效？**
A: 重启服务器 (`uv run main.py`) 即可加载新配置。

**Q: 可以添加多个相同provider的配置吗？**
A: 可以。例如为不同温度、token数创建多个GPT-4配置，给它们不同的名称即可。
