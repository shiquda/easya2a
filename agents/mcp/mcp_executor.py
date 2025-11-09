"""
MCP Agent Executor

A2A协议执行器实现，支持MCP工具调用和流式响应
"""

import logging
import traceback
from typing import Any

from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Part, TaskState, TextPart
from a2a.utils import new_agent_text_message

from agents.base import BaseAgentExecutor
from agents.mcp.mcp_agent import MCPAgent


logger = logging.getLogger(__name__)


class MCPAgentExecutor(BaseAgentExecutor):
    """
    MCP Agent的A2A执行器

    支持从RequestContext提取消息并执行流式响应的ReAct循环
    在每个步骤发送中间消息，避免客户端超时
    """

    def __init__(self, agent: MCPAgent):
        """
        初始化MCP Agent Executor

        Args:
            agent: MCPAgent实例
        """
        super().__init__(agent)

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        执行Agent逻辑（流式响应版本）

        在ReAct循环的每个步骤发送中间消息事件，
        确保客户端及时收到响应，避免超时

        Args:
            context: 请求上下文
            event_queue: 事件队列
        """
        try:
            # 创建 TaskUpdater 用于发送中间状态更新
            updater = TaskUpdater(event_queue, context.task_id, context.context_id)

            # 确保工具已加载（懒加载）
            await self.agent._ensure_tools_loaded()

            # 从context提取输入
            user_message = await self.prepare_input(context)

            if not user_message:
                # 发送最终错误消息（使用 Message 事件）
                await event_queue.enqueue_event(
                    new_agent_text_message("No message content found")
                )
                return

            logger.info(f"MCP Agent '{self.agent.name}' processing: {user_message[:100]}...")

            # 立即发送初始状态更新，避免客户端超时
            initial_message = updater.new_agent_message(
                parts=[Part(root=TextPart(text="🔄 Processing your request..."))]
            )
            await updater.update_status(
                TaskState.working,
                message=initial_message,
                final=False
            )

            # 准备对话历史
            messages = self.agent._build_initial_messages(user_message)

            # ReAct循环（流式响应版本）
            for iteration in range(self.agent.mcp_config.max_tool_calls + 1):
                logger.info(
                    f"MCP Agent '{self.agent.name}' starting iteration {iteration + 1}/"
                    f"{self.agent.mcp_config.max_tool_calls + 1}"
                )

                # LLM推理
                response = await self.agent.llm_manager.chat(messages)
                assistant_message = response.content

                logger.info(
                    f"LLM response (iteration {iteration + 1}): "
                    f"{assistant_message[:500]}{'...' if len(assistant_message) > 500 else ''}"
                )

                # 检查是否需要调用工具
                tool_calls = self.agent._parse_tool_calls(assistant_message)

                logger.info(
                    f"Parsed {len(tool_calls)} tool call(s) from LLM response"
                )

                if not tool_calls:
                    # 没有工具调用，这是最终答案
                    logger.info(
                        f"MCP Agent '{self.agent.name}' got final answer "
                        f"(iteration {iteration + 1}, length: {len(assistant_message)} chars)"
                    )
                    # 发送最终答案
                    logger.info(f"Sending final answer as Message event...")
                    await event_queue.enqueue_event(
                        new_agent_text_message(assistant_message)
                    )
                    logger.info(f"Final answer sent successfully")
                    return

                # 执行工具调用
                logger.info(
                    f"MCP Agent '{self.agent.name}' executing {len(tool_calls)} tool call(s) "
                    f"(iteration {iteration + 1})"
                )

                # 发送思考过程（使用 TaskUpdater 发送中间状态更新，不会关闭队列）
                thinking_text = f"🤔 Thinking... (calling {len(tool_calls)} tool(s))"
                thinking_message = updater.new_agent_message(
                    parts=[Part(root=TextPart(text=thinking_text))]
                )
                await updater.update_status(
                    TaskState.working,
                    message=thinking_message,
                    final=False  # 这是中间更新，不是最终结果
                )

                # 将助手消息添加到历史
                messages.append({"role": "assistant", "content": assistant_message})

                # 调用工具并收集结果
                tool_results = []
                for tool_call in tool_calls:
                    result = await self.agent._execute_tool_call(tool_call)
                    tool_results.append(result)

                    # 发送工具执行进度（使用 TaskUpdater 发送中间状态更新）
                    tool_name = tool_call.get("tool", "unknown")
                    if "error" in result:
                        progress_text = f"❌ Tool '{tool_name}' failed: {result['error']}"
                    else:
                        progress_text = f"✓ Tool '{tool_name}' executed"

                    progress_message = updater.new_agent_message(
                        parts=[Part(root=TextPart(text=progress_text))]
                    )
                    await updater.update_status(
                        TaskState.working,
                        message=progress_message,
                        final=False  # 这是中间更新
                    )

                # 将工具结果添加到历史
                tool_message = self.agent._format_tool_results(tool_results)
                messages.append({"role": "user", "content": tool_message})

            # 达到最大迭代次数
            logger.warning(
                f"MCP Agent '{self.agent.name}' reached max iterations "
                f"({self.agent.mcp_config.max_tool_calls})"
            )
            await event_queue.enqueue_event(
                new_agent_text_message(
                    "Sorry, I couldn't complete the task within the allowed tool calls."
                )
            )

        except Exception as e:
            logger.error(
                f"Error in MCP Agent '{self.agent.name}' execution: {e}\n"
                f"Traceback: {traceback.format_exc()}"
            )
            # 发送错误消息给客户端
            await event_queue.enqueue_event(
                new_agent_text_message(
                    f"Sorry, an error occurred while processing your request: {str(e)}"
                )
            )
            raise

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
