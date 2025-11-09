# MCP Agent 使用指南

## 概述

MCP (Model Context Protocol) Agent 是一个强大的 AI Agent，能够调用外部 MCP 服务器提供的工具，如 GitHub 探索、Web 搜索、数据库访问等。

## 快速开始

### 1. 安装依赖

MCP 支持已经集成到项目中，运行以下命令确保所有依赖已安装：

```bash
uv sync
```

### 2. 配置 MCP 服务器

在 `config/agents.yaml` 中添加 MCP 服务器配置。

#### 方式一：远程 SSE 服务器（推荐）

无需安装，直接连接远程服务：

```yaml
mcp_servers:
  deepwiki-remote:
    transport: sse  # 或 streamable_http
    url: "https://mcp.deepwiki.com/sse"
    description: "GitHub repository exploration (remote)"
```

**优势**:
- ✅ 无需安装 npm 包
- ✅ 无需配置 API Key
- ✅ 开箱即用
- ✅ 适合生产环境

#### 方式二：本地 stdio 服务器

需要安装 npm 包：

```yaml
mcp_servers:
  deepwiki-local:
    transport: stdio
    command: npx
    args:
      - "-y"
      - "@deepwiki/mcp"
    env:
      DEEPWIKI_API_KEY: "${DEEPWIKI_API_KEY}"
    description: "GitHub repository exploration (local)"
```

**需要**:
- Node.js 和 npm
- 相应的 MCP 服务器包
- API Key（如需要）

### 3. 配置 MCP Agent

在 `config/agents.yaml` 的 `agents` 列表中添加：

```yaml
agents:
  - name: research-assistant
    description: "AI research assistant with tool capabilities"
    type: mcp
    host: 0.0.0.0
    port: 9010
    llm_provider: openai-gpt4
    extra:
      mcp_config:
        servers:
          - deepwiki-remote  # 使用远程服务器
        max_tool_calls: 5
```

### 4. 设置环境变量

```bash
# OpenAI API Key（用于LLM推理）
export OPENAI_API_KEY=sk-...

# 如果使用本地 MCP 服务器，可能需要额外的 API Key
# export DEEPWIKI_API_KEY=your-key-here
```

### 5. 启动服务器

```bash
uv run main.py
```

### 6. 测试 Agent

```bash
# 获取 Agent Card
curl http://localhost:9010/api/v1/agent/card

# 发送请求
curl -X POST http://localhost:9010/api/v1/agent/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{
      "role": "user",
      "content": "Search for the latest updates on MCP Python SDK"
    }]
  }'
```

## MCP 服务器

### 传输协议

MCP 支持三种传输协议：

| 协议 | 适用场景 | 配置 | 优缺点 |
|------|---------|------|--------|
| **SSE** | 远程 HTTP 服务 | 只需 `url` | ✅ 无需安装<br>✅ 跨平台<br>✅ 适合生产 |
| **Streamable HTTP** | 远程 HTTP 服务 | 只需 `url` | 同 SSE |
| **stdio** | 本地进程通信 | 需 `command`, `args` | ✅ 低延迟<br>❌ 需安装<br>❌ 平台相关 |

### 官方支持的 MCP 服务器

| 服务器 | 远程 URL | 本地 NPM 包 | 功能 | 需要 API Key |
|--------|----------|-------------|------|--------------|
| **DeepWiki** | `https://mcp.deepwiki.com/sse` | `@deepwiki/mcp` | GitHub 仓库探索 | 远程：否<br>本地：是 |
| **Brave Search** | - | `@modelcontextprotocol/server-brave-search` | Web 搜索 | 是 |
| **SQLite** | - | `@modelcontextprotocol/server-sqlite` | 数据库访问 | 否 |
| **Filesystem** | - | `@modelcontextprotocol/server-filesystem` | 文件系统访问 | 否 |
| **GitHub** | - | `@modelcontextprotocol/server-github` | GitHub API | 是 |

### 安装 MCP 服务器

MCP 服务器通常使用 npx 动态安装，无需手动安装。首次运行时会自动下载。

如果需要全局安装：

```bash
npm install -g @deepwiki/mcp
npm install -g @modelcontextprotocol/server-brave-search
```

## 配置选项

### MCP Agent 配置 (`mcp_config`)

| 字段 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `servers` | list[str] | 是 | - | 引用的 MCP 服务器名称列表 |
| `system_prompt` | str | 否 | 自动生成 | 自定义系统提示词 |
| `max_tool_calls` | int | 否 | 5 | 单次对话最大工具调用次数 |
| `tool_choice` | str | 否 | "auto" | 工具调用策略：auto/required/none |

### MCP 服务器配置 (`mcp_servers`)

| 字段 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `transport` | str | 否 | "stdio" | 传输协议：stdio/sse/streamable_http |
| `command` | str | 是 | - | 启动命令 |
| `args` | list[str] | 否 | [] | 命令参数 |
| `env` | dict | 否 | {} | 环境变量（支持 ${VAR} 格式） |
| `cwd` | str | 否 | null | 工作目录 |
| `description` | str | 否 | null | 服务器描述 |

## 工作原理

MCP Agent 使用 **ReAct (Reasoning and Acting)** 模式：

```
1. 用户输入
   ↓
2. LLM 分析：是否需要工具？
   ↓
3a. 不需要 → 直接回答
   ↓
3b. 需要 → 调用工具
   ↓
4. 获取工具结果
   ↓
5. LLM 综合结果生成回答
   ↓
6. 返回响应
```

### 示例交互

**用户**: "Search for MCP Python SDK on GitHub"

**Agent 思考**: 需要使用 deepwiki 工具搜索 GitHub

**工具调用**:
```json
{
  "tool": "deepwiki:search_repositories",
  "arguments": {
    "query": "MCP Python SDK"
  }
}
```

**工具结果**: [返回搜索结果]

**Agent 响应**: 根据搜索结果生成综合回答

## 故障排除

### 问题：MCP 服务器连接失败

**检查**:
1. 确认 npx 已安装：`npx --version`
2. 检查环境变量是否设置
3. 查看日志中的错误信息

**解决**:
```bash
# 手动测试 MCP 服务器
npx -y @deepwiki/mcp
```

### 问题：工具调用不工作

**检查**:
1. 查看 Agent 日志，确认工具是否被识别
2. 验证 MCP 服务器配置正确
3. 确认 LLM API Key 有效

**调试**:
```bash
# 设置日志级别为 DEBUG
# 在 config/agents.yaml 中:
system:
  log_level: DEBUG
```

### 问题：工具调用超时

**解决**:
- 增加 `max_tool_calls` 限制
- 优化系统提示词，让 LLM 更快决策
- 使用更快的 LLM 模型（如 gpt-3.5-turbo）

## 最佳实践

### 1. 编写清晰的系统提示词

```yaml
extra:
  mcp_config:
    system_prompt: |
      You are a research assistant with access to:
      - GitHub repository search (deepwiki)
      - Web search (brave-search)

      When users ask questions:
      1. Identify if tools are needed
      2. Use appropriate tools to gather info
      3. Synthesize clear answers
      4. Always cite sources
```

### 2. 限制工具调用次数

避免无限循环，设置合理的 `max_tool_calls`：

```yaml
mcp_config:
  max_tool_calls: 5  # 推荐值：3-10
```

### 3. 选择合适的 LLM

- **GPT-4**: 更好的推理能力，适合复杂任务
- **GPT-3.5 Turbo**: 更快更便宜，适合简单任务

### 4. 监控和日志

使用 DEBUG 日志级别观察工具调用过程：

```yaml
system:
  log_level: DEBUG
```

## 进阶使用

### 自定义 MCP 服务器

可以创建自己的 MCP 服务器提供专用工具。参考 [MCP 官方文档](https://modelcontextprotocol.io/)。

### 多工具协作

配置多个 MCP 服务器，让 Agent 自动选择合适的工具：

```yaml
mcp_config:
  servers:
    - deepwiki      # GitHub 搜索
    - brave-search  # Web 搜索
    - sqlite-db     # 数据库查询
```

## 参考资料

- [MCP 官方文档](https://modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP 服务器列表](https://github.com/modelcontextprotocol/servers)
- [MCP 设计文档](./MCP_AGENT_DESIGN.md)
- [MCP 调研报告](./docs/MCP_AGENT_RESEARCH.md)
