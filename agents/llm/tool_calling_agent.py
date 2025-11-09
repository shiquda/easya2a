"""
Tool-Calling LLM Agent实现

使用LLM和工具执行器进行智能对话，支持工具调用循环
"""

import logging
import traceback
from typing import Any

from agents.base import BaseAgent
from core.llm_manager import LLMManager
from core.tool_executor import ToolExecutor


logger = logging.getLogger(__name__)


class ToolCallingLLMAgent(BaseAgent):
    """
    支持工具调用的LLM Agent

    该Agent可以调用外部工具来完成任务，通过多轮对话实现复杂的功能。

    工作流程:
    1. 接收用户输入
    2. 调用LLM获取响应
    3. 如果LLM请求调用工具：
       a. 执行工具
       b. 将结果返回给LLM
       c. 重复步骤2-3
    4. 返回最终响应

    使用示例:
        # 创建工具执行器
        tool_executor = ToolExecutor()

        # 注册工具
        @tool_executor.register_tool
        async def get_weather(location: str) -> dict:
            return {"temperature": "20°C", "location": location}

        # 创建Agent
        agent = ToolCallingLLMAgent(
            name="Assistant",
            llm_manager=llm_manager,
            tool_executor=tool_executor,
            system_prompt="You are a helpful assistant with access to tools."
        )

        # 使用Agent
        response = await agent.invoke("What's the weather in Paris?")
    """

    def __init__(
        self,
        llm_manager: LLMManager,
        tool_executor: ToolExecutor,
        name: str = "ToolCallingLLMAgent",
        system_prompt: str | None = None,
        max_iterations: int | None = None,
    ):
        """
        初始化Tool-Calling LLM Agent

        Args:
            llm_manager: LLM管理器实例
            tool_executor: 工具执行器实例
            name: Agent名称
            system_prompt: 系统提示词（可选）
            max_iterations: 最大工具调用迭代次数（可选，默认使用LLM配置的值）
        """
        super().__init__(name=name)
        self.llm_manager = llm_manager
        self.tool_executor = tool_executor
        self.system_prompt = system_prompt or "You are a helpful AI assistant with access to tools."

        # 最大迭代次数：优先使用传入参数，否则使用LLM配置，最后默认为10
        self.max_iterations = (
            max_iterations
            or getattr(llm_manager.config, 'max_tool_iterations', None)
            or 10
        )

        logger.info(
            f"Initialized ToolCallingLLMAgent '{name}' with max_iterations={self.max_iterations}"
        )

    async def invoke(self, input_data: Any = None) -> str:
        """
        执行带工具调用的LLM对话

        Args:
            input_data: 用户输入消息（字符串或消息列表）

        Returns:
            LLM的最终响应文本
        """
        # 准备初始消息列表
        messages = self._prepare_messages(input_data)

        logger.debug(
            f"ToolCallingLLMAgent '{self.name}' starting invoke:\n"
            f"  Messages count: {len(messages)}\n"
            f"  Max iterations: {self.max_iterations}"
        )

        # 工具调用循环
        for iteration in range(self.max_iterations):
            logger.debug(f"Iteration {iteration + 1}/{self.max_iterations}")

            try:
                # 调用LLM
                response = await self.llm_manager.chat(messages)

                logger.debug(
                    f"LLM response (iteration {iteration + 1}):\n"
                    f"  Content: {response.content[:100] if response.content else 'None'}...\n"
                    f"  Tool calls: {len(response.tool_calls) if response.tool_calls else 0}\n"
                    f"  Finish reason: {response.finish_reason}"
                )

                # 如果没有工具调用，返回结果
                if not response.tool_calls:
                    logger.info(
                        f"ToolCallingLLMAgent '{self.name}' completed "
                        f"in {iteration + 1} iteration(s)"
                    )
                    return response.content or "No response content"

                # 将助手的消息添加到历史（包含tool_calls）
                # 注意：OpenAI要求将包含tool_calls的完整消息添加到历史
                messages.append({
                    "role": "assistant",
                    "content": response.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in response.tool_calls
                    ]
                })

                logger.info(f"Executing {len(response.tool_calls)} tool call(s)...")

                # 执行所有工具调用
                tool_results = await self.tool_executor.execute_all(response.tool_calls)

                # 将工具结果添加到消息历史
                messages.extend(tool_results)

                logger.debug(f"Tool results added to message history")

            except Exception as e:
                logger.error(
                    f"ToolCallingLLMAgent '{self.name}' error (iteration {iteration + 1}):\n"
                    f"  Error: {e}\n"
                    f"  Error Type: {type(e).__name__}\n"
                    f"  Traceback:\n{traceback.format_exc()}"
                )
                return f"Sorry, I encountered an error: {str(e)}"

        # 达到最大迭代次数
        logger.warning(
            f"ToolCallingLLMAgent '{self.name}' reached max iterations "
            f"({self.max_iterations})"
        )
        return (
            f"I've reached the maximum number of tool calls ({self.max_iterations}). "
            "Please try rephrasing your request or breaking it into smaller tasks."
        )

    def _prepare_messages(self, input_data: Any) -> list[dict[str, Any]]:
        """
        准备消息列表

        Args:
            input_data: 输入数据（字符串或消息列表）

        Returns:
            标准化的消息列表
        """
        # 如果没有输入，使用默认消息
        if input_data is None:
            input_data = "Hello!"

        # 如果输入已经是消息列表，直接使用
        if isinstance(input_data, list):
            messages = input_data.copy()
        # 否则当作字符串处理
        else:
            messages = [{"role": "user", "content": str(input_data)}]

        # 如果第一条消息不是system消息，添加system prompt
        if not messages or messages[0].get("role") != "system":
            messages.insert(0, {"role": "system", "content": self.system_prompt})

        return messages

    async def initialize(self):
        """初始化Agent资源"""
        # 确保LLM Manager已初始化
        if not self.llm_manager._client:
            await self.llm_manager.initialize()

        # 记录可用工具
        available_tools = self.tool_executor.list_tools()
        logger.info(
            f"ToolCallingLLMAgent '{self.name}' initialized with {len(available_tools)} tools: "
            f"{available_tools}"
        )

    async def cleanup(self):
        """清理Agent资源"""
        # LLM Manager由外部管理，不在这里关闭
        logger.info(f"ToolCallingLLMAgent '{self.name}' cleanup completed")
