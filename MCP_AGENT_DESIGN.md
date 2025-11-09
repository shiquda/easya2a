# MCP Agent 设计方案

## 1. 概述

本文档详细说明了如何在现有的 A2A 多智能体系统中集成 MCP (Model Context Protocol) 客户端功能，使 Agent 能够调用外部 MCP 服务器提供的工具。

## 2. MCP 协议基础

### 2.1 什么是 MCP？

Model Context Protocol (MCP) 是由 Anthropic 于 2024年11月推出的开放协议，用于标准化 AI 应用与外部数据源和工具的连接方式。

**核心特性**：
- 标准化的工具、资源和提示词接口
- 支持多种传输方式（stdio、SSE、Streamable HTTP）
- 客户端-服务器架构
- 丰富的生态系统（官方和社区 MCP 服务器）

### 2.2 官方 MCP Python SDK

**包名**: `mcp`
**安装**: `uv add mcp`
**最新规范**: 2025-06-18

**核心组件**：
```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 配置服务器参数
server_params = StdioServerParameters(
    command="uv",                    # 启动命令
    args=["run", "server.py"],       # 命令参数
    env={"API_KEY": "xxx"},          # 环境变量
)

# 建立连接
async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()

        # 列出工具
        tools = await session.list_tools()

        # 调用工具
        result = await session.call_tool("tool_name", {"arg": "value"})
```

### 2.3 工具调用流程

1. **列出可用工具**: `session.list_tools()` 返回工具元数据（名称、描述、输入schema）
2. **调用工具**: `session.call_tool(name, arguments)` 返回 `CallToolResult`
3. **处理结果**:
   - `result.content` - 兼容旧版的文本内容列表
   - `result.structuredContent` - 2025-06-18 规范的结构化输出

## 3. 设计方案

### 3.1 配置结构设计

#### 3.1.1 全局 MCP 服务器配置

在 `config/agents.yaml` 中添加全局 `mcp_servers` 配置段：

```yaml
# 全局 MCP 服务器配置
mcp_servers:
  deepwiki:
    transport: stdio
    command: npx
    args: ["-y", "@deepwiki/mcp"]
    env:
      DEEPWIKI_API_KEY: ${DEEPWIKI_API_KEY}
    description: "GitHub repository exploration"

  brave-search:
    transport: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-brave-search"]
    env:
      BRAVE_API_KEY: ${BRAVE_API_KEY}
    description: "Web search using Brave Search API"

  filesystem:
    transport: stdio
    command: npx
    args:
      - "-y"
      - "@modelcontextprotocol/server-filesystem"
      - "/path/to/allowed/directory"
    description: "Filesystem access (read-only)"

  sqlite:
    transport: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-sqlite"]
    env:
      DB_PATH: ${SQLITE_DB_PATH}
    description: "SQLite database access"
```

#### 3.1.2 Agent 配置引用 MCP 服务器

```yaml
agents:
  - name: research-agent
    description: "Research agent with web search and GitHub access"
    type: mcp
    host: 0.0.0.0
    port: 9005

    # 引用 LLM Provider（用于工具调用决策和响应生成）
    llm_provider: gpt4

    # MCP 配置
    mcp_config:
      # 引用要使用的 MCP 服务器列表
      servers:
        - deepwiki
        - brave-search

      # 系统提示词（指导 Agent 如何使用工具）
      system_prompt: |
        You are a research assistant with access to the following tools:
        - GitHub repository exploration (deepwiki)
        - Web search (brave-search)

        Use these tools to help answer user questions thoroughly.

      # 工具调用配置
      tool_choice: auto  # auto, required, none
      max_tool_calls: 5  # 单次对话最大工具调用次数
```

### 3.2 配置模型定义

在 `core/config.py` 中添加：

```python
from enum import Enum
from typing import Literal

class MCPTransport(str, Enum):
    """MCP传输协议类型"""
    STDIO = "stdio"
    SSE = "sse"
    STREAMABLE_HTTP = "streamable_http"

class MCPServerConfigModel(BaseModel):
    """MCP服务器配置模型"""
    transport: MCPTransport = Field(default=MCPTransport.STDIO)
    command: str = Field(...)  # 启动命令
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)  # 环境变量
    cwd: str | None = Field(default=None)  # 工作目录
    description: str | None = Field(default=None)

    @field_validator("env", mode="before")
    @classmethod
    def expand_env_vars(cls, v: dict[str, str]) -> dict[str, str]:
        """展开环境变量"""
        result = {}
        for key, value in v.items():
            if value.startswith("${") and value.endswith("}"):
                var_name = value[2:-1]
                result[key] = os.getenv(var_name, "")
            else:
                result[key] = value
        return result

class MCPAgentConfigModel(BaseModel):
    """MCP Agent 专用配置"""
    servers: list[str] = Field(...)  # 引用的 MCP 服务器名称列表
    system_prompt: str | None = Field(default=None)
    tool_choice: Literal["auto", "required", "none"] = Field(default="auto")
    max_tool_calls: int = Field(default=5, gt=0, le=20)

class AppConfigModel(BaseModel):
    """应用总配置模型（扩展现有）"""
    system: SystemConfigModel = Field(default_factory=SystemConfigModel)
    llm_providers: dict[str, LLMConfigModel] = Field(default_factory=dict)
    mcp_servers: dict[str, MCPServerConfigModel] = Field(default_factory=dict)  # 新增
    agents: list[AgentConfigModel] = Field(...)
```

### 3.3 MCP 客户端管理器

创建 `core/mcp_manager.py` 来管理 MCP 客户端连接：

```python
"""
MCP客户端管理器

功能：
- 管理多个MCP服务器连接
- 提供统一的工具调用接口
- 连接池管理和生命周期管理
"""

import logging
from typing import Any
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Tool, CallToolResult

from core.config import MCPServerConfigModel

logger = logging.getLogger(__name__)

class MCPClientManager:
    """
    MCP客户端管理器

    管理与单个MCP服务器的连接
    """

    def __init__(self, name: str, config: MCPServerConfigModel):
        self.name = name
        self.config = config
        self._session: ClientSession | None = None
        self._tools: list[Tool] = []
        self._initialized = False

    async def initialize(self):
        """初始化连接到MCP服务器"""
        if self._initialized:
            return

        logger.info(f"Initializing MCP client '{self.name}'...")

        # 构建服务器参数
        server_params = StdioServerParameters(
            command=self.config.command,
            args=self.config.args,
            env=self.config.env,
            cwd=self.config.cwd,
        )

        # 建立连接（注意：这里需要在 Agent 的生命周期内维护）
        # 实际实现时，需要使用后台任务或生命周期管理
        logger.info(
            f"MCP client '{self.name}' connecting via {self.config.transport} "
            f"(command: {self.config.command})"
        )

        # TODO: 实现连接管理
        # 这里需要特殊处理，因为 stdio_client 是 async context manager
        # 需要在 Agent 初始化时启动，在清理时关闭

        self._initialized = True
        logger.info(f"MCP client '{self.name}' initialized")

    async def list_tools(self) -> list[Tool]:
        """列出可用工具"""
        if not self._session:
            raise RuntimeError(f"MCP client '{self.name}' not connected")

        result = await self._session.list_tools()
        self._tools = result.tools
        return self._tools

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> CallToolResult:
        """调用工具"""
        if not self._session:
            raise RuntimeError(f"MCP client '{self.name}' not connected")

        logger.debug(f"MCP client '{self.name}' calling tool '{tool_name}' with args: {arguments}")
        result = await self._session.call_tool(tool_name, arguments)
        logger.debug(f"MCP client '{self.name}' tool call completed")

        return result

    async def cleanup(self):
        """清理资源"""
        if self._session:
            # 关闭会话
            self._session = None
        self._initialized = False
        logger.info(f"MCP client '{self.name}' cleaned up")


class MCPManagerPool:
    """
    MCP管理器池

    管理多个MCP客户端连接
    """

    def __init__(self):
        self._clients: dict[str, MCPClientManager] = {}

    def register_server(self, name: str, config: MCPServerConfigModel):
        """注册MCP服务器"""
        if name in self._clients:
            logger.warning(f"MCP server '{name}' already registered, skipping")
            return

        client = MCPClientManager(name, config)
        self._clients[name] = client
        logger.info(f"Registered MCP server '{name}'")

    async def initialize_all(self):
        """初始化所有客户端"""
        for name, client in self._clients.items():
            await client.initialize()

    def get_client(self, name: str) -> MCPClientManager:
        """获取MCP客户端"""
        if name not in self._clients:
            raise KeyError(f"MCP server '{name}' not found")
        return self._clients[name]

    async def get_all_tools(self, server_names: list[str]) -> dict[str, list[Tool]]:
        """获取指定服务器的所有工具"""
        tools_by_server = {}
        for name in server_names:
            client = self.get_client(name)
            tools = await client.list_tools()
            tools_by_server[name] = tools
        return tools_by_server

    async def cleanup_all(self):
        """清理所有客户端"""
        for client in self._clients.values():
            await client.cleanup()


# 全局MCP管理器池
_mcp_pool: MCPManagerPool | None = None

def get_mcp_pool() -> MCPManagerPool:
    """获取全局MCP管理器池"""
    global _mcp_pool
    if _mcp_pool is None:
        _mcp_pool = MCPManagerPool()
    return _mcp_pool
```

### 3.4 MCP Agent 实现

创建 `agents/mcp/mcp_agent.py`:

```python
"""
MCP Agent 实现

集成 MCP 工具调用与 LLM 推理的智能 Agent
"""

import json
import logging
from typing import Any

from agents.base import BaseAgent
from core.llm_manager import LLMManager
from core.mcp_manager import MCPManagerPool
from core.config import MCPAgentConfigModel

logger = logging.getLogger(__name__)

class MCPAgent(BaseAgent):
    """
    MCP工具调用Agent

    结合LLM和MCP工具，实现ReAct模式的智能Agent：
    1. LLM分析用户请求，决定是否需要调用工具
    2. 如需调用工具，解析工具名称和参数
    3. 调用MCP工具获取结果
    4. 将工具结果反馈给LLM生成最终响应
    """

    def __init__(
        self,
        name: str,
        llm_manager: LLMManager,
        mcp_pool: MCPManagerPool,
        mcp_config: MCPAgentConfigModel,
    ):
        super().__init__(name=name)
        self.llm_manager = llm_manager
        self.mcp_pool = mcp_pool
        self.mcp_config = mcp_config

        # 工具缓存
        self._tools_cache: dict[str, Any] = {}

    async def initialize(self):
        """初始化Agent，加载MCP工具"""
        logger.info(f"MCP Agent '{self.name}' initializing...")

        # 获取所有配置的MCP服务器的工具
        tools_by_server = await self.mcp_pool.get_all_tools(
            self.mcp_config.servers
        )

        # 构建工具索引（工具名 -> 服务器名）
        for server_name, tools in tools_by_server.items():
            for tool in tools:
                # 使用 "server:tool" 格式避免工具名冲突
                tool_key = f"{server_name}:{tool.name}"
                self._tools_cache[tool_key] = {
                    "server": server_name,
                    "tool": tool,
                }

        logger.info(
            f"MCP Agent '{self.name}' loaded {len(self._tools_cache)} tools "
            f"from {len(tools_by_server)} servers"
        )

    async def invoke(self, input_data: Any = None) -> str:
        """
        执行Agent逻辑

        实现ReAct循环：
        1. 思考（LLM分析）
        2. 行动（调用工具）
        3. 观察（获取工具结果）
        4. 重复直到得出最终答案
        """
        if isinstance(input_data, str):
            user_message = input_data
        elif isinstance(input_data, dict):
            user_message = input_data.get("content", str(input_data))
        else:
            user_message = str(input_data)

        # 准备对话历史
        messages = self._build_initial_messages(user_message)

        # ReAct循环
        for iteration in range(self.mcp_config.max_tool_calls + 1):
            logger.debug(f"MCP Agent '{self.name}' iteration {iteration}")

            # LLM推理
            response = await self.llm_manager.chat(messages)
            assistant_message = response.content

            # 检查是否需要调用工具
            tool_calls = self._parse_tool_calls(assistant_message)

            if not tool_calls:
                # 没有工具调用，直接返回响应
                logger.info(f"MCP Agent '{self.name}' completed without tool calls")
                return assistant_message

            # 执行工具调用
            logger.info(
                f"MCP Agent '{self.name}' executing {len(tool_calls)} tool call(s)"
            )

            # 将助手消息添加到历史
            messages.append({"role": "assistant", "content": assistant_message})

            # 调用工具并收集结果
            tool_results = []
            for tool_call in tool_calls:
                result = await self._execute_tool_call(tool_call)
                tool_results.append(result)

            # 将工具结果添加到历史
            tool_message = self._format_tool_results(tool_results)
            messages.append({"role": "user", "content": tool_message})

        # 达到最大迭代次数
        logger.warning(
            f"MCP Agent '{self.name}' reached max iterations "
            f"({self.mcp_config.max_tool_calls})"
        )
        return "Sorry, I couldn't complete the task within the allowed tool calls."

    def _build_initial_messages(self, user_message: str) -> list[dict[str, str]]:
        """构建初始消息列表"""
        system_prompt = self.mcp_config.system_prompt or self._build_default_system_prompt()

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

    def _build_default_system_prompt(self) -> str:
        """构建默认系统提示词"""
        tools_description = self._format_tools_for_prompt()

        return f"""You are a helpful AI assistant with access to external tools.

Available tools:
{tools_description}

To use a tool, respond with a JSON block in this format:
```json
{{
  "tool": "server:tool_name",
  "arguments": {{"arg1": "value1", "arg2": "value2"}}
}}
```

After receiving tool results, use them to formulate your final answer.
"""

    def _format_tools_for_prompt(self) -> str:
        """格式化工具描述用于提示词"""
        lines = []
        for tool_key, tool_info in self._tools_cache.items():
            tool = tool_info["tool"]
            lines.append(f"- {tool_key}: {tool.description}")
        return "\n".join(lines)

    def _parse_tool_calls(self, message: str) -> list[dict[str, Any]]:
        """
        从LLM响应中解析工具调用

        期望格式：
        ```json
        {"tool": "server:tool_name", "arguments": {...}}
        ```
        """
        tool_calls = []

        # 简单实现：查找JSON代码块
        import re
        json_blocks = re.findall(r'```json\s*(\{.*?\})\s*```', message, re.DOTALL)

        for block in json_blocks:
            try:
                parsed = json.loads(block)
                if "tool" in parsed and "arguments" in parsed:
                    tool_calls.append(parsed)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON block: {block}")

        return tool_calls

    async def _execute_tool_call(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        """执行单个工具调用"""
        tool_key = tool_call["tool"]
        arguments = tool_call["arguments"]

        if tool_key not in self._tools_cache:
            return {
                "tool": tool_key,
                "error": f"Tool '{tool_key}' not found",
            }

        tool_info = self._tools_cache[tool_key]
        server_name = tool_info["server"]
        tool_name = tool_info["tool"].name

        try:
            client = self.mcp_pool.get_client(server_name)
            result = await client.call_tool(tool_name, arguments)

            # 提取结果
            if result.structuredContent:
                content = result.structuredContent
            elif result.content:
                # 提取文本内容
                content = "\n".join(
                    item.text for item in result.content
                    if hasattr(item, "text")
                )
            else:
                content = "Tool executed successfully (no output)"

            return {
                "tool": tool_key,
                "result": content,
            }

        except Exception as e:
            logger.error(f"Error calling tool '{tool_key}': {e}")
            return {
                "tool": tool_key,
                "error": str(e),
            }

    def _format_tool_results(self, results: list[dict[str, Any]]) -> str:
        """格式化工具结果为消息"""
        lines = ["Tool execution results:"]
        for result in results:
            tool_name = result["tool"]
            if "error" in result:
                lines.append(f"\n[{tool_name}] Error: {result['error']}")
            else:
                lines.append(f"\n[{tool_name}] Result:\n{result['result']}")
        return "\n".join(lines)
```

### 3.5 集成到 main.py

在 `main.py` 中添加 MCP Agent 支持：

```python
from core.mcp_manager import get_mcp_pool, MCPClientManager
from core.config import MCPAgentConfigModel
from agents.mcp.mcp_agent import MCPAgent
from agents.mcp.mcp_executor import MCPAgentExecutor

def build_agent_executor(agent_config: AgentConfigModel, config_manager: ConfigManager) -> BaseAgentExecutor:
    """构建Agent执行器"""

    # ... 现有代码 ...

    elif agent_config.type == "mcp":
        # MCP Agent
        if not agent_config.llm_provider:
            raise ValueError(f"MCP agent '{agent_config.name}' requires llm_provider")

        # 获取LLM配置
        llm_config_model = config_manager.get_llm_provider(agent_config.llm_provider)
        llm_config = LLMConfig.from_config_model(llm_config_model)

        # 注册LLM管理器
        register_llm_manager(agent_config.llm_provider, llm_config)
        llm_manager = get_llm_manager(agent_config.llm_provider)

        # 解析MCP配置
        mcp_config = MCPAgentConfigModel(**agent_config.extra.get("mcp_config", {}))

        # 创建MCP Agent
        agent = MCPAgent(
            name=agent_config.name,
            llm_manager=llm_manager,
            mcp_pool=get_mcp_pool(),
            mcp_config=mcp_config,
        )

        return MCPAgentExecutor(agent)

    else:
        raise ValueError(f"Unknown agent type: {agent_config.type}")


async def main():
    """主入口"""
    # ... 现有代码 ...

    # 初始化MCP管理器池
    mcp_pool = get_mcp_pool()
    for name, mcp_config in config_manager.get_all_mcp_servers().items():
        mcp_pool.register_server(name, mcp_config)

    await mcp_pool.initialize_all()

    # ... 现有代码 ...

    try:
        await server.start()
    finally:
        # 清理MCP连接
        await mcp_pool.cleanup_all()
```

## 4. 使用示例

### 4.1 配置文件示例

```yaml
# config/agents.yaml

system:
  log_level: DEBUG

# MCP服务器配置
mcp_servers:
  deepwiki:
    transport: stdio
    command: npx
    args: ["-y", "@deepwiki/mcp"]
    env:
      DEEPWIKI_API_KEY: ${DEEPWIKI_API_KEY}
    description: "GitHub repository exploration"

  brave:
    transport: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-brave-search"]
    env:
      BRAVE_API_KEY: ${BRAVE_API_KEY}

# LLM配置
llm_providers:
  gpt4:
    provider: openai
    model: gpt-4
    api_key: ${OPENAI_API_KEY}
    temperature: 0.7

# Agent配置
agents:
  - name: researcher
    description: "AI researcher with web search and GitHub access"
    type: mcp
    host: 0.0.0.0
    port: 9005
    llm_provider: gpt4
    extra:
      mcp_config:
        servers:
          - deepwiki
          - brave
        system_prompt: |
          You are a research assistant. Use web search and GitHub tools to answer questions.
        max_tool_calls: 5
```

### 4.2 测试 MCP Agent

```bash
# 启动服务器
uv run main.py

# 测试Agent Card
curl http://localhost:9005/api/v1/agent/card

# 使用A2A协议调用
curl -X POST http://localhost:9005/api/v1/agent/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "Search for the latest MCP Python SDK updates on GitHub"
      }
    ]
  }'
```

## 5. 技术挑战与解决方案

### 5.1 连接生命周期管理

**挑战**: `stdio_client` 是异步上下文管理器，需要在整个 Agent 生命周期内保持连接。

**解决方案**:
- 在 `MCPClientManager` 中使用后台任务维护连接
- 在 Agent 初始化时建立连接
- 在 Agent 清理时关闭连接

### 5.2 工具调用格式

**挑战**: 需要让 LLM 理解工具格式并正确调用。

**解决方案**:
- 方案A（当前）: 使用 JSON 代码块格式，在系统提示词中说明
- 方案B（推荐）: 使用 OpenAI 的 Function Calling API
  - 将 MCP 工具转换为 OpenAI function schema
  - 使用 `tools` 参数传递给 LLM
  - 自动解析 `tool_calls` 响应

### 5.3 多轮对话状态管理

**挑战**: A2A 协议支持多轮对话，需要维护对话历史。

**解决方案**:
- 在 `MCPAgentExecutor` 中维护对话历史
- 每次调用时传递完整历史给 `MCPAgent.invoke()`

## 6. 未来优化方向

### 6.1 支持更多传输协议
- SSE (Server-Sent Events)
- Streamable HTTP

### 6.2 工具调用优化
- 集成 OpenAI Function Calling
- 支持并行工具调用
- 工具调用结果缓存

### 6.3 可观测性
- 工具调用追踪
- 性能监控
- 调试日志增强

### 6.4 安全性
- 工具权限控制
- 参数验证
- 速率限制

## 7. 参考资料

- [MCP 官方文档](https://modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP 官方服务器](https://github.com/modelcontextprotocol/servers)
- [MCP 规范 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18)
