"""
MCP Agent 实现

集成 MCP 工具调用与 LLM 推理的智能 Agent
"""

import json
import logging
import re
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

    使用示例:
        # 创建MCP Pool和LLM Manager
        mcp_pool = get_mcp_pool()
        llm_manager = get_llm_manager("gpt4")

        # 创建配置
        mcp_config = MCPAgentConfigModel(
            servers=["deepwiki", "brave-search"],
            max_tool_calls=5
        )

        # 创建Agent
        agent = MCPAgent(
            name="researcher",
            llm_manager=llm_manager,
            mcp_pool=mcp_pool,
            mcp_config=mcp_config
        )

        # 初始化
        await agent.initialize()

        # 使用
        response = await agent.invoke("Search for MCP Python SDK on GitHub")
    """

    def __init__(
        self,
        name: str,
        llm_manager: LLMManager,
        mcp_pool: MCPManagerPool,
        mcp_config: MCPAgentConfigModel,
    ):
        """
        初始化MCP Agent

        Args:
            name: Agent名称
            llm_manager: LLM管理器
            mcp_pool: MCP管理器池
            mcp_config: MCP Agent配置
        """
        super().__init__(name=name)
        self.llm_manager = llm_manager
        self.mcp_pool = mcp_pool
        self.mcp_config = mcp_config

        # 工具缓存: tool_key -> {server, tool}
        self._tools_cache: dict[str, Any] = {}

    async def initialize(self):
        """初始化Agent，加载MCP工具"""
        logger.info(f"MCP Agent '{self.name}' initializing...")

        if not self.mcp_config.servers:
            logger.warning(f"MCP Agent '{self.name}' has no configured servers")
            return

        # 获取所有配置的MCP服务器的工具
        tools_by_server = await self.mcp_pool.get_all_tools(
            self.mcp_config.servers
        )

        # 构建工具索引（工具名 -> 服务器名）
        tool_count = 0
        for server_name, tools in tools_by_server.items():
            for tool in tools:
                # 使用 "server:tool" 格式避免工具名冲突
                tool_key = f"{server_name}:{tool.name}"
                self._tools_cache[tool_key] = {
                    "server": server_name,
                    "tool": tool,
                }
                tool_count += 1

        logger.info(
            f"MCP Agent '{self.name}' loaded {tool_count} tools "
            f"from {len(tools_by_server)} servers"
        )

        # 打印工具列表（调试）
        if logger.isEnabledFor(logging.DEBUG):
            for tool_key, tool_info in self._tools_cache.items():
                tool = tool_info["tool"]
                logger.debug(f"  - {tool_key}: {tool.description}")

    async def invoke(self, input_data: Any = None) -> str:
        """
        执行Agent逻辑

        实现ReAct循环：
        1. 思考（LLM分析）
        2. 行动（调用工具）
        3. 观察（获取工具结果）
        4. 重复直到得出最终答案

        Args:
            input_data: 用户输入（字符串或包含content的字典）

        Returns:
            Agent的响应文本
        """
        # 提取用户消息
        if isinstance(input_data, str):
            user_message = input_data
        elif isinstance(input_data, dict):
            user_message = input_data.get("content", str(input_data))
        else:
            user_message = str(input_data)

        logger.info(f"MCP Agent '{self.name}' processing: {user_message[:100]}...")

        # 准备对话历史
        messages = self._build_initial_messages(user_message)

        # ReAct循环
        for iteration in range(self.mcp_config.max_tool_calls + 1):
            logger.debug(f"MCP Agent '{self.name}' iteration {iteration + 1}")

            # LLM推理
            response = await self.llm_manager.chat(messages)
            assistant_message = response.content

            logger.debug(
                f"LLM response (iteration {iteration + 1}): "
                f"{assistant_message[:200]}..."
            )

            # 检查是否需要调用工具
            tool_calls = self._parse_tool_calls(assistant_message)

            if not tool_calls:
                # 没有工具调用，直接返回响应
                logger.info(
                    f"MCP Agent '{self.name}' completed without tool calls "
                    f"(iteration {iteration + 1})"
                )
                return assistant_message

            # 执行工具调用
            logger.info(
                f"MCP Agent '{self.name}' executing {len(tool_calls)} tool call(s) "
                f"(iteration {iteration + 1})"
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
        """
        构建初始消息列表

        Args:
            user_message: 用户消息

        Returns:
            消息列表
        """
        system_prompt = self.mcp_config.system_prompt or self._build_default_system_prompt()

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

    def _build_default_system_prompt(self) -> str:
        """
        构建默认系统提示词

        Returns:
            系统提示词
        """
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

You can call multiple tools in sequence if needed. After receiving tool results, use them to formulate your final answer.

If you don't need to use any tools to answer the question, respond directly without any JSON blocks.
"""

    def _format_tools_for_prompt(self) -> str:
        """
        格式化工具描述用于提示词

        Returns:
            工具描述文本
        """
        if not self._tools_cache:
            return "(No tools available)"

        lines = []
        for tool_key, tool_info in self._tools_cache.items():
            tool = tool_info["tool"]
            # 添加工具名称和描述
            lines.append(f"- {tool_key}: {tool.description}")

            # 添加输入schema信息（简化）
            if hasattr(tool, "inputSchema") and tool.inputSchema:
                schema = tool.inputSchema
                if "properties" in schema:
                    args = ", ".join(schema["properties"].keys())
                    lines.append(f"  Arguments: {args}")

        return "\n".join(lines)

    def _parse_tool_calls(self, message: str) -> list[dict[str, Any]]:
        """
        从LLM响应中解析工具调用

        期望格式：
        ```json
        {"tool": "server:tool_name", "arguments": {...}}
        ```

        Args:
            message: LLM响应消息

        Returns:
            工具调用列表
        """
        tool_calls = []

        # 查找所有JSON代码块
        json_blocks = re.findall(r'```json\s*(\{.*?\})\s*```', message, re.DOTALL)

        for block in json_blocks:
            try:
                parsed = json.loads(block)
                if "tool" in parsed and "arguments" in parsed:
                    tool_calls.append(parsed)
                    logger.debug(f"Parsed tool call: {parsed['tool']}")
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON block: {block[:100]}... Error: {e}")

        return tool_calls

    async def _execute_tool_call(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        """
        执行单个工具调用

        Args:
            tool_call: 工具调用信息

        Returns:
            工具执行结果
        """
        tool_key = tool_call["tool"]
        arguments = tool_call.get("arguments", {})

        if tool_key not in self._tools_cache:
            logger.warning(f"Tool '{tool_key}' not found in cache")
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
                text_parts = []
                for item in result.content:
                    if hasattr(item, "text"):
                        text_parts.append(item.text)
                content = "\n".join(text_parts) if text_parts else "Tool executed successfully"
            else:
                content = "Tool executed successfully (no output)"

            logger.info(f"Tool '{tool_key}' executed successfully")

            return {
                "tool": tool_key,
                "result": content,
            }

        except Exception as e:
            logger.error(f"Error calling tool '{tool_key}': {e}", exc_info=True)
            return {
                "tool": tool_key,
                "error": str(e),
            }

    def _format_tool_results(self, results: list[dict[str, Any]]) -> str:
        """
        格式化工具结果为消息

        Args:
            results: 工具结果列表

        Returns:
            格式化的消息文本
        """
        lines = ["Tool execution results:"]

        for result in results:
            tool_name = result["tool"]
            if "error" in result:
                lines.append(f"\n[{tool_name}] Error: {result['error']}")
            else:
                result_str = str(result['result'])
                # 限制结果长度避免消息过长
                if len(result_str) > 2000:
                    result_str = result_str[:2000] + "\n...(truncated)"
                lines.append(f"\n[{tool_name}] Result:\n{result_str}")

        return "\n".join(lines)
