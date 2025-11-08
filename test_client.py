"""
A2A Agent 测试客户端
用于测试Echo Agent的功能
"""

import asyncio
import logging
from a2a.client import ClientFactory
from a2a.client.helpers import create_text_message_object
from a2a.types import Task  # 导入Task类型


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


async def test_echo_agent():
    """测试Echo Agent的基本功能"""
    # 创建客户端 - 使用ClientFactory.connect
    client = await ClientFactory.connect("http://localhost:9999")

    try:
        # 1. 获取Agent Card信息
        logger.info("=== Testing Agent Card Retrieval ===")
        agent_card = await client.get_card()
        logger.info(f"Agent Name: {agent_card.name}")
        logger.info(f"Agent Description: {agent_card.description}")
        logger.info(f"Agent Version: {agent_card.version}")
        logger.info(f"Agent Skills: {[skill.name for skill in agent_card.skills]}")
        logger.info(f"Input Modes: {agent_card.input_modes if hasattr(agent_card, 'input_modes') else 'N/A'}")
        logger.info(f"Output Modes: {agent_card.output_modes if hasattr(agent_card, 'output_modes') else 'N/A'}")
        logger.info(f"Streaming Support: {agent_card.streaming_support if hasattr(agent_card, 'streaming_support') else 'N/A'}")

        # 2. 发送测试消息
        logger.info("\n=== Testing Message Exchange ===")
        test_messages = [
            "Hello, Echo Agent!",
            "这是一个中文测试",
            "Testing A2A protocol implementation",
        ]

        for test_text in test_messages:
            logger.info(f"\nSending: {test_text}")

            # 创建消息 - content参数需要是关键字参数
            message = create_text_message_object(content=test_text)

            # 发送消息并接收响应 - send_message返回AsyncIterator
            response_iterator = client.send_message(message)

            logger.info("Receiving responses:")
            async for response in response_iterator:
                if isinstance(response, Task):
                    logger.info(f"Task ID: {response.id}")
                    logger.info(f"Task Status: {response.status}")
                    # 获取响应消息
                    if response.output:
                        for event in response.output:
                            if hasattr(event, 'content'):
                                for content in event.content:
                                    if hasattr(content, 'text'):
                                        logger.info(f"Received: {content.text}")
                elif hasattr(response, 'parts'):
                    # 处理Message响应
                    for part in response.parts:
                        if hasattr(part, 'text'):
                            logger.info(f"Received: {part.text}")

        logger.info("\n=== All Tests Completed Successfully ===")

    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        raise


async def main():
    """主函数"""
    logger.info("Starting A2A Agent Test Client...")
    logger.info("Make sure the A2A server is running on http://localhost:9999")
    logger.info("-" * 60)

    try:
        await test_echo_agent()
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
