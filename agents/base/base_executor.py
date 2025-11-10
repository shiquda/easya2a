"""
基础Executor抽象类

连接BaseAgent和A2A协议的桥梁
"""

import logging
from abc import ABC
from typing import Any

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

from agents.base.base_agent import BaseAgent


logger = logging.getLogger(__name__)


class BaseAgentExecutor(AgentExecutor, ABC):
    """
    Agent Executor基类

    继承自A2A的AgentExecutor，连接BaseAgent和A2A协议

    使用示例:
        class MyAgentExecutor(BaseAgentExecutor):
            def __init__(self):
                agent = MyAgent()
                super().__init__(agent)
    """

    def __init__(self, agent: BaseAgent):
        """
        初始化Executor

        Args:
            agent: BaseAgent实例
        """
        self.agent = agent

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        执行Agent逻辑

        Args:
            context: 请求上下文
            event_queue: 事件队列
        """
        # 打印接收到的消息（限制500字符）
        context_str = str(context)[:500]
        logger.info(f"Agent '{self.agent.name}' received request: {context_str}")

        # 从context提取输入（子类可以重写此方法自定义输入处理）
        input_data = await self.prepare_input(context)

        # 调用agent处理
        result = await self.agent.invoke(input_data)

        # 格式化输出（子类可以重写此方法自定义输出格式）
        await self.send_output(result, event_queue)

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        取消执行（默认不支持，子类可重写）

        Args:
            context: 请求上下文
            event_queue: 事件队列
        """
        raise NotImplementedError("Cancel operation not supported")

    async def prepare_input(self, context: RequestContext) -> Any:
        """
        从RequestContext准备输入数据

        子类可以重写此方法来自定义输入处理逻辑
        默认返回None（适用于无状态的Agent）

        Args:
            context: 请求上下文

        Returns:
            准备好的输入数据
        """
        return None

    async def send_output(self, result: Any, event_queue: EventQueue) -> None:
        """
        发送输出到事件队列

        子类可以重写此方法来自定义输出格式
        默认将结果转为字符串并作为文本消息发送

        Args:
            result: Agent处理结果
            event_queue: 事件队列
        """
        # 默认行为：转为字符串并发送文本消息
        message_text = str(result) if result is not None else ""
        await event_queue.enqueue_event(new_agent_text_message(message_text))


class SimpleAgentExecutor(BaseAgentExecutor):
    """
    简化的Executor实现

    用于快速创建简单的无状态Agent
    直接调用agent.invoke()，不处理上下文

    使用示例:
        agent = MyAgent()
        executor = SimpleAgentExecutor(agent)
    """

    async def prepare_input(self, context: RequestContext) -> Any:
        """简单实现：不处理上下文，返回None"""
        return None
