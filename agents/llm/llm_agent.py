"""
LLM Agent实现

使用LLM（如OpenAI）进行智能对话的Agent
"""

import logging
import traceback
from typing import Any

from agents.base import BaseAgent
from core.llm_manager import LLMManager


logger = logging.getLogger(__name__)


class LLMAgent(BaseAgent):
    """
    LLM驱动的智能Agent

    使用LLMManager调用大语言模型进行对话

    使用示例:
        # 创建或获取LLM Manager
        from core.llm_manager import get_llm_manager
        llm_manager = get_llm_manager("gpt4")

        # 创建Agent
        agent = LLMAgent(
            name="Assistant",
            llm_manager=llm_manager,
            system_prompt="You are a helpful assistant."
        )

        # 使用Agent
        response = await agent.invoke("Hello!")
    """

    def __init__(
        self,
        llm_manager: LLMManager,
        name: str = "LLMAgent",
        system_prompt: str | None = None,
    ):
        """
        初始化LLM Agent

        Args:
            llm_manager: LLM管理器实例
            name: Agent名称
            system_prompt: 系统提示词（可选）
        """
        super().__init__(name=name)
        self.llm_manager = llm_manager
        self.system_prompt = system_prompt or "You are a helpful AI assistant."

    async def invoke(self, input_data: Any = None) -> str:
        """
        执行LLM对话

        Args:
            input_data: 用户输入消息（字符串或消息列表）

        Returns:
            LLM的响应文本
        """
        # 准备消息列表
        messages = self._prepare_messages(input_data)

        logger.debug(
            f"LLM Agent '{self.name}' preparing to invoke with:\n"
            f"  Messages count: {len(messages)}\n"
            f"  System prompt: {self.system_prompt[:50]}..."
        )

        try:
            # 调用LLM
            logger.debug(f"LLM Agent '{self.name}' calling LLM manager...")
            response = await self.llm_manager.chat(messages)
            logger.debug(f"LLM Agent '{self.name}' received response from LLM manager")

            logger.info(
                f"LLM Agent '{self.name}' processed message "
                f"(tokens: {response.usage.total_tokens})"
            )

            return response.content

        except Exception as e:
            logger.error(
                f"LLM Agent '{self.name}' error:\n"
                f"  Error: {e}\n"
                f"  Error Type: {type(e).__name__}\n"
                f"  Messages count: {len(messages)}\n"
                f"  Traceback:\n{traceback.format_exc()}"
            )
            return f"Sorry, I encountered an error: {str(e)}"

    def _prepare_messages(self, input_data: Any) -> list[dict[str, str]]:
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
            messages = input_data
        # 否则当作字符串处理
        else:
            messages = [{"role": "user", "content": str(input_data)}]

        # 如果第一条消息不是system消息，添加system prompt
        if not messages or messages[0].get("role") != "system":
            messages.insert(0, {"role": "system", "content": self.system_prompt})

        return messages


class StreamingLLMAgent(LLMAgent):
    """
    支持流式输出的LLM Agent

    TODO: 实现流式响应，需要调整executor支持
    """

    async def invoke_stream(self, input_data: Any = None):
        """
        流式执行LLM对话

        Args:
            input_data: 用户输入消息

        Yields:
            LLM响应的文本块
        """
        messages = self._prepare_messages(input_data)

        logger.debug(f"Streaming LLM Agent '{self.name}' preparing to invoke stream")

        try:
            async for chunk in self.llm_manager.chat_stream(messages):
                yield chunk

            logger.debug(f"Streaming LLM Agent '{self.name}' completed stream")

        except Exception as e:
            logger.error(
                f"LLM Agent '{self.name}' streaming error:\n"
                f"  Error: {e}\n"
                f"  Error Type: {type(e).__name__}\n"
                f"  Traceback:\n{traceback.format_exc()}"
            )
            yield f"Sorry, I encountered an error: {str(e)}"
