"""
Agent Executor - 实现A2A协议的核心agent逻辑
"""

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message


class EchoAgent:
    """简单的Echo Agent实现"""

    async def invoke(self) -> str:
        """处理消息并返回响应"""
        return "Echo Agent响应: Hello from Echo Agent!"


class EchoAgentExecutor(AgentExecutor):
    """
    Echo Agent Executor - 实现A2A协议的agent执行器

    功能：
    1. 接收请求并回复消息
    2. 支持事件队列处理
    3. 展示A2A协议的基本实现
    """

    def __init__(self):
        self.agent = EchoAgent()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        执行agent逻辑

        Args:
            context: 请求上下文，包含消息历史等信息
            event_queue: 事件队列，用于发送响应消息
        """
        # 调用agent获取结果
        result = await self.agent.invoke()

        # 将结果发送到事件队列
        await event_queue.enqueue_event(new_agent_text_message(result))

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        """取消执行（本示例不支持）"""
        raise Exception('cancel not supported')


# 创建executor实例
executor = EchoAgentExecutor()
