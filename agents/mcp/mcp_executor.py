"""
MCP Agent Executor

A2A协议执行器实现，支持MCP工具调用
"""

import logging
from typing import Any

from a2a.server.agent_execution import RequestContext

from agents.base import BaseAgentExecutor
from agents.mcp.mcp_agent import MCPAgent


logger = logging.getLogger(__name__)


class MCPAgentExecutor(BaseAgentExecutor):
    """
    MCP Agent的A2A执行器

    支持从RequestContext提取消息历史并传递给MCP Agent
    """

    def __init__(self, agent: MCPAgent):
        """
        初始化MCP Agent Executor

        Args:
            agent: MCPAgent实例
        """
        super().__init__(agent)

    async def prepare_input(self, context: RequestContext) -> Any:
        """
        从RequestContext提取消息作为输入

        从context中提取当前用户消息（MCP Agent内部会维护ReAct循环）

        Args:
            context: 请求上下文

        Returns:
            用户消息字符串
        """
        # 提取当前用户消息
        if context.message and context.message.parts:
            current_text = ""
            for part in context.message.parts:
                # 提取文本内容
                if hasattr(part, "text") and part.text:
                    current_text += part.text
                elif hasattr(part, "root") and hasattr(part.root, "text"):
                    current_text += part.root.text

            if current_text:
                logger.debug(f"Extracted message: {current_text[:100]}...")
                return current_text

        logger.debug("No message content found in context")
        return None
