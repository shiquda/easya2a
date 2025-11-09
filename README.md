# Multi-Agent A2A System

基于 `a2a-sdk` 实现的多智能体 A2A (Agent2Agent) 协议系统。

> 🎯 **无需编程！** 通过编辑配置文件即可创建和部署各种AI Agent，支持OpenAI GPT、Claude等多种LLM。

## 项目特点

本项目展示了如何使用 A2A 协议构建可扩展的多智能体系统：

- ✅ **零代码配置**：通过YAML配置文件即可创建Agent，无需编程
- ✅ **多Agent部署**：单进程内运行多个独立Agent
- ✅ **多种Agent类型**：支持LLM对话、工具调用、MCP外部工具集成等
- ✅ **LLM集成**：支持OpenAI、Azure OpenAI等多种大语言模型
- ✅ **工具能力**：通过MCP协议访问GitHub、Web搜索、数据库等外部工具
- ✅ **模块化架构**：清晰的代码组织和可扩展设计
- ✅ **A2A协议标准**：完整实现A2A协议规范
- ✅ **独立Agent设计**：每个Agent完全独立，依赖关系由外部管理

## 架构概览

```
agentic-web/
├── agents/              # Agent实现
│   ├── base/           # 基础抽象类
│   ├── echo/           # Echo Agent（示例）
│   ├── llm/            # LLM驱动的Agent和工具调用Agent
│   └── mcp/            # MCP协议Agent（外部工具集成）
├── core/               # 核心模块
│   ├── config.py       # 配置管理
│   ├── llm_manager.py  # 统一LLM调用管理
│   └── server.py       # 多端口服务器管理
├── config/             # 配置文件
│   └── agents.yaml     # Agent配置（这是你唯一需要编辑的文件！）
├── main.py             # 统一启动入口
└── pyproject.toml      # 项目依赖
```

## 🚀 无需编程构建Agent

**好消息！** 你不需要编写任何代码就可以创建和部署各种AI Agent。只需编辑一个配置文件 `config/agents.yaml`。

### 支持的Agent类型

| 类型 | 说明 | 使用场景 | 需要LLM |
|------|------|----------|---------|
| **echo** | 简单回声Agent | 测试、演示 | ❌ |
| **llm** | LLM对话Agent | 通用对话、翻译、文本处理 | ✅ |
| **tool_calling** | 带本地工具调用的LLM Agent | 需要调用本地函数获取信息 | ✅ |
| **mcp** | 集成MCP外部工具的Agent | GitHub探索、Web搜索、数据库查询 | ✅ |

### 三步创建你的第一个Agent

#### 步骤1：准备配置文件

```bash
# 复制示例配置
cp config/agents.example.yaml config/agents.yaml
```

#### 步骤2：设置API密钥（如果使用LLM）

```bash
# Windows
set OPENAI_API_KEY=sk-your-key-here

# Linux/Mac
export OPENAI_API_KEY=sk-your-key-here
```

#### 步骤3：编辑配置文件

打开 `config/agents.yaml`，找到要启用的Agent，取消注释即可！

### 配置示例：创建不同类型的Agent

#### 示例1：创建一个翻译Agent（最简单）

在 `config/agents.yaml` 中添加：

```yaml
agents:
  - name: translator
    description: "Professional translation agent"
    type: llm
    host: 0.0.0.0
    port: 9004
    llm_provider: openai-gpt4  # 引用LLM配置
    extra:
      system_prompt: |
        You are a professional translator.
        Translate user input to the target language they specify.
```

**就是这样！** 启动服务器后，你就有了一个翻译Agent。

#### 示例2：创建一个GitHub探索Agent（带工具能力）

```yaml
agents:
  - name: github-explorer
    description: "GitHub repository exploration assistant"
    type: mcp
    host: 0.0.0.0
    port: 9010
    llm_provider: openai-gpt4
    extra:
      mcp_config:
        servers:
          - deepwiki-remote  # 使用DeepWiki工具
        system_prompt: |
          You are a GitHub exploration assistant.
          Help users find and understand repositories.
```

这个Agent可以探索GitHub仓库、搜索代码、理解项目结构！

#### 示例3：创建一个编程助手

```yaml
llm_providers:
  # 先配置一个适合代码的LLM
  openai-gpt4-coder:
    provider: openai
    model: "gpt-4"
    api_key: "${OPENAI_API_KEY}"
    temperature: 0.3  # 低温度=更精确的代码
    max_tokens: 4000

agents:
  - name: code-helper
    description: "Programming assistant"
    type: llm
    host: 0.0.0.0
    port: 9005
    llm_provider: openai-gpt4-coder
    extra:
      system_prompt: |
        You are an expert programming assistant.
        Provide clear, well-commented code with explanations.
```

### 常见配置模式

#### 🔧 配置Azure OpenAI

```yaml
llm_providers:
  azure-gpt4:
    provider: azure_openai
    model: "your-deployment-name"  # Azure部署名称
    api_key: "${AZURE_OPENAI_KEY}"
    base_url: "https://your-resource.openai.azure.com"
    api_version: "2024-04-01-preview"
    temperature: 0.7
```

#### 🔧 使用本地Ollama模型

```yaml
llm_providers:
  local-llama:
    provider: openai  # Ollama兼容OpenAI API
    model: "llama2"
    api_key: "not-needed"
    base_url: "http://localhost:11434/v1"
    temperature: 0.8
```

#### 🔧 添加MCP工具服务器

```yaml
mcp_servers:
  # 远程DeepWiki服务（推荐，无需安装）
  deepwiki-remote:
    transport: sse
    url: "https://mcp.deepwiki.com/sse"
    description: "GitHub repository exploration"

  # 本地Brave搜索（需要npm安装）
  brave-search:
    transport: stdio
    command: npx
    args:
      - "-y"
      - "@modelcontextprotocol/server-brave-search"
    env:
      BRAVE_API_KEY: "${BRAVE_API_KEY}"
```

## 快速开始

### 1. 安装依赖

推荐使用 `uv` 包管理器（更快）：

```bash
uv sync
```

或使用传统的 pip：

```bash
pip install -e .
```

### 2. 配置Agent

```bash
# 复制示例配置文件
cp config/agents.example.yaml config/agents.yaml

# 编辑配置文件，启用需要的Agent
# Windows: notepad config/agents.yaml
# Linux/Mac: nano config/agents.yaml
```

### 3. 设置环境变量（如果使用LLM Agent）

```bash
# Windows
set OPENAI_API_KEY=your-api-key-here

# Linux/Mac
export OPENAI_API_KEY=your-api-key-here
```

### 4. 启动服务器

```bash
uv run main.py
```

服务器将根据配置文件在多个端口上启动所有Agent：

```
============================================================
Multi-Agent A2A Server Starting...
============================================================
Agent Status:
  - echo: echo @ http://localhost:9001
  - gpt-assistant: llm @ http://localhost:9002
  - translator: llm @ http://localhost:9004
  - github-explorer: mcp @ http://localhost:9010
============================================================
```

### 5. 测试Agent

```bash
# 使用官方调试工具（推荐）
npx @a2aprotocol/inspector http://localhost:9001

# 或使用curl测试Agent Card
curl http://localhost:9001/api/v1/agent/card

# 或使用项目提供的测试客户端
uv run test_client.py
```

## 配置详解

配置文件 `config/agents.yaml` 分为四个主要部分：

### 1. 系统配置

```yaml
system:
  log_level: INFO  # 日志级别: DEBUG, INFO, WARNING, ERROR
  log_format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

### 2. LLM Providers配置

**核心概念**：所有LLM配置统一管理，Agent通过引用provider名称使用。

```yaml
llm_providers:
  # 定义一个provider
  openai-gpt4:
    provider: openai              # 提供商类型: openai, azure_openai
    model: "gpt-4"               # 模型名称
    api_key: "${OPENAI_API_KEY}" # API密钥（支持环境变量）
    temperature: 0.7             # 温度参数 (0.0-2.0)
    max_tokens: 2000             # 最大token数
    timeout: 60.0                # 请求超时（秒）
    max_retries: 3               # 最大重试次数

  # 可以定义多个provider，用于不同用途
  openai-gpt4-coder:
    provider: openai
    model: "gpt-4"
    api_key: "${OPENAI_API_KEY}"
    temperature: 0.3  # 更低温度用于代码生成
    max_tokens: 4000
```

### 3. MCP服务器配置（可选）

如果要使用MCP Agent，需要配置MCP服务器：

```yaml
mcp_servers:
  # 远程服务器（推荐，无需安装）
  deepwiki-remote:
    transport: sse
    url: "https://mcp.deepwiki.com/sse"
    description: "GitHub repository exploration"

  # 本地服务器（需要npm安装）
  brave-search:
    transport: stdio
    command: npx
    args:
      - "-y"
      - "@modelcontextprotocol/server-brave-search"
    env:
      BRAVE_API_KEY: "${BRAVE_API_KEY}"
```

**可用的MCP服务器**：
- **DeepWiki**：GitHub仓库探索（无需安装，使用远程服务）
- **Brave Search**：Web搜索（需要Brave API key）
- **SQLite**：数据库查询
- **Filesystem**：文件系统访问

更多MCP服务器：https://github.com/modelcontextprotocol/servers

### 4. Agent配置

```yaml
agents:
  # Echo Agent示例（不需要LLM）
  - name: echo
    description: "A simple echo agent"
    type: echo
    host: 0.0.0.0
    port: 9001
    provider:  # 可选的provider信息
      organization: "Demo Org"
      url: "https://example.com"

  # LLM Agent示例
  - name: gpt-assistant
    description: "GPT-4 powered assistant"
    type: llm
    host: 0.0.0.0
    port: 9002
    llm_provider: openai-gpt4  # 引用全局定义的provider
    extra:
      system_prompt: "You are a helpful assistant."

  # MCP Agent示例
  - name: github-explorer
    description: "GitHub exploration assistant"
    type: mcp
    host: 0.0.0.0
    port: 9010
    llm_provider: openai-gpt4
    extra:
      mcp_config:
        servers:
          - deepwiki-remote  # 引用MCP服务器
        system_prompt: "You are a GitHub exploration assistant."
        max_tool_calls: 5  # 最大工具调用次数
        tool_choice: auto  # auto, required, none
```

### 配置最佳实践

1. **API密钥管理**：使用环境变量 `${VAR_NAME}` 格式，不要硬编码
2. **LLM复用**：为不同用途定义不同的provider（通用/代码/快速）
3. **端口分配**：确保每个Agent的端口唯一
4. **MCP服务器**：优先使用远程服务，避免本地安装复杂度
5. **参考示例**：查看 `config/agents.example.yaml` 获取完整配置示例

## 核心模块

### 1. 配置管理 (core/config.py)

- 从YAML加载配置
- 类型安全的配置访问
- 环境变量替换
- 配置验证（端口唯一性检查等）

### 2. LLM管理器 (core/llm_manager.py)

- 统一的LLM调用接口
- 支持多个LLM提供商（OpenAI、Azure OpenAI）
- 异步调用和流式响应
- Token使用统计
- 自动重试和错误处理

### 3. 服务器管理 (core/server.py)

- 单进程多端口管理
- 并发运行多个Agent
- 优雅的启动和关闭
- 信号处理

### 4. Agent基类 (agents/base/)

- `BaseAgent`: 业务逻辑抽象基类
- `BaseAgentExecutor`: A2A协议执行器基类
- `SimpleAgentExecutor`: 简化的Executor实现

## Agent类型详解

### Echo Agent (agents/echo/)

**用途**：测试和演示

简单的回声Agent，用于测试A2A协议的基础功能。

**配置示例**：
```yaml
agents:
  - name: echo
    type: echo
    port: 9001
```

### LLM Agent (agents/llm/)

**用途**：通用对话、翻译、文本处理

基于大语言模型的智能Agent，可以处理各种对话任务。

**配置示例**：
```yaml
agents:
  - name: assistant
    type: llm
    port: 9002
    llm_provider: openai-gpt4
    extra:
      system_prompt: "You are a helpful assistant."
```

**典型应用**：
- 通用对话助手
- 专业翻译
- 文本摘要
- 内容创作

### Tool Calling Agent (agents/llm/)

**用途**：需要调用本地Python函数获取信息

带有本地工具调用能力的LLM Agent，可以调用预定义的Python函数。

**配置示例**：
```yaml
agents:
  - name: weather-assistant
    type: tool_calling
    port: 9011
    llm_provider: openai-gpt4-native  # 使用支持tool calling的provider
    extra:
      system_prompt: "You are a weather assistant."
      max_iterations: 10
```

**工具调用模式**：
- **native**：使用OpenAI原生Tool Calling API（推荐）
- **prompt**：通过提示词让模型输出JSON格式

**典型应用**：
- 天气查询
- 计算器
- 日期时间查询
- 本地数据查询

### MCP Agent (agents/mcp/)

**用途**：集成外部工具（GitHub、Web搜索、数据库等）

最强大的Agent类型，通过MCP (Model Context Protocol) 协议访问各种外部工具。

**配置示例**：
```yaml
# 首先配置MCP服务器
mcp_servers:
  deepwiki-remote:
    transport: sse
    url: "https://mcp.deepwiki.com/sse"

# 然后创建MCP Agent
agents:
  - name: research-assistant
    type: mcp
    port: 9010
    llm_provider: openai-gpt4
    extra:
      mcp_config:
        servers:
          - deepwiki-remote
        system_prompt: "You are a research assistant."
        max_tool_calls: 5
        tool_choice: auto
```

**可用工具**：
- **DeepWiki**：探索GitHub仓库、搜索代码、理解项目
- **Brave Search**：实时Web搜索
- **SQLite**：查询数据库
- **Filesystem**：读取文件

**典型应用**：
- GitHub代码探索
- 技术研究助手
- 数据分析助手
- 文档查询

## 开发指南（高级用户）

> **注意**：如果只需创建Agent，不需要阅读此部分。本部分适合需要扩展系统功能的开发者。

### 创建新的Agent类型

如果现有的四种Agent类型不能满足需求，可以通过编程创建新类型：

**1. 继承BaseAgent**：

```python
# agents/custom/my_agent.py
from agents.base import BaseAgent

class MyAgent(BaseAgent):
    async def invoke(self, input_data=None):
        # 实现你的逻辑
        return "Response"
```

**2. 创建Executor**：

```python
# agents/custom/my_executor.py
from agents.base import SimpleAgentExecutor
from .my_agent import MyAgent

class MyAgentExecutor(SimpleAgentExecutor):
    def __init__(self, name="MyAgent"):
        agent = MyAgent(name=name)
        super().__init__(agent)
```

**3. 在main.py中注册**：

```python
def build_agent_executor(agent_config):
    if agent_config.type == "custom":
        return MyAgentExecutor(name=agent_config.name)
    # ...
```

**4. 添加到配置文件**：

```yaml
agents:
  - name: my-custom-agent
    type: custom
    port: 9020
```

### 扩展LLM Provider

在 `core/llm_manager.py` 中添加新的provider：

```python
elif self.config.provider == LLMProvider.ANTHROPIC:
    # 实现Anthropic客户端
    self._client = AnthropicClient(...)
```

## A2A协议特性

本项目完整实现A2A协议规范：

- ✅ **Agent Card**：完整的Agent元数据
- ✅ **消息交换**：支持文本消息的发送和接收
- ✅ **流式响应**：支持流式输出（Streaming）
- ✅ **多轮对话**：支持上下文保持的多轮对话
- ✅ **Provider信息**：可配置Agent提供者信息
- ✅ **工具调用**：支持LLM工具调用（Tool Calling）
- ✅ **MCP集成**：通过MCP协议访问外部工具

## 调试和测试

### 使用A2A Inspector（推荐）

官方提供的可视化调试工具：

```bash
npx @a2aprotocol/inspector http://localhost:9001
```

### 使用curl测试

```bash
# 获取Agent Card
curl http://localhost:9001/api/v1/agent/card

# 发送消息（需要更复杂的JSON payload）
# 建议使用A2A Inspector或项目提供的测试脚本
```

### 使用测试脚本

```bash
# 测试Agent Card
./scripts/test_agent_card.sh http://localhost:9001

# Windows
scripts\test_agent_card.bat http://localhost:9001
```

详细调试指南请参考 `DEBUG_GUIDE.md`。

## 常见问题

### Q: 如何使用本地Ollama模型？

A: 配置如下：

```yaml
llm_providers:
  local-llama:
    provider: openai  # Ollama兼容OpenAI API
    model: "llama2"
    api_key: "not-needed"
    base_url: "http://localhost:11434/v1"
```

### Q: 如何添加新的MCP工具？

A:

1. 在 `mcp_servers` 中配置工具服务器
2. 在MCP Agent的 `mcp_config.servers` 中引用

### Q: 端口已被占用怎么办？

A: 在 `config/agents.yaml` 中修改对应Agent的端口号。

### Q: 如何部署多个相同类型的Agent？

A: 复制Agent配置，修改name和port即可：

```yaml
agents:
  - name: assistant-1
    type: llm
    port: 9002
    llm_provider: openai-gpt4

  - name: assistant-2
    type: llm
    port: 9003
    llm_provider: openai-gpt35  # 可以使用不同的provider
```

## 环境要求

- Python 3.13+
- a2a-sdk[http-server] >= 0.3.11
- uvicorn >= 0.30.0
- openai >= 1.0.0 (使用LLM Agent时)
- pydantic >= 2.0.0

可选依赖：
- mcp >= 1.2.0 (使用MCP Agent时)
- Node.js (使用本地MCP服务器时)

## 相关资源

- [A2A 协议官方文档](https://a2a-protocol.org/)
- [A2A Python SDK](https://github.com/a2aproject/a2a-python)
- [A2A 示例项目](https://github.com/a2aproject/a2a-samples)
- [MCP 协议文档](https://modelcontextprotocol.io/)
- [MCP 服务器列表](https://github.com/modelcontextprotocol/servers)

## 贡献和反馈

欢迎提交Issue和Pull Request！

## 许可证

MIT
