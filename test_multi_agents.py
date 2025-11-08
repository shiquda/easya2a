"""
测试新的多Agent系统
"""
import asyncio
import logging
from a2a.client import ClientFactory
from a2a.client.helpers import create_text_message_object
from a2a.types import Task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_agent(url: str, agent_name: str, test_message: str):
    """测试单个Agent"""
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing {agent_name} at {url}")
    logger.info(f"{'='*60}")

    try:
        client = await ClientFactory.connect(url)

        # 获取Agent Card
        card = await client.get_card()
        logger.info(f"✓ Agent Name: {card.name}")
        logger.info(f"✓ Description: {card.description}")

        # 发送测试消息
        logger.info(f"\nSending message: {test_message}")
        message = create_text_message_object(content=test_message)
        response_iterator = client.send_message(message)

        async for response in response_iterator:
            if isinstance(response, Task):
                logger.info(f"Task ID: {response.id}")
                logger.info(f"Task Status: {response.status}")
                if response.output:
                    for event in response.output:
                        if hasattr(event, 'content'):
                            for content in event.content:
                                if hasattr(content, 'text'):
                                    logger.info(f"✓ Response: {content.text}")

        logger.info(f"✓ {agent_name} test completed successfully!\n")
        return True

    except Exception as e:
        logger.error(f"✗ {agent_name} test failed: {e}\n")
        return False


async def main():
    """测试所有Agent"""
    logger.info("=" * 60)
    logger.info("Multi-Agent System Test")
    logger.info("=" * 60)

    agents = [
        ("http://localhost:9001", "Echo Agent", "Hello from test!"),
        ("http://localhost:9002", "GPT Assistant", "你好，请用一句话介绍一下你自己"),
        ("http://localhost:9003", "GPT Coder", "写一个Python函数计算斐波那契数列"),
    ]

    results = []
    for url, name, message in agents:
        result = await test_agent(url, name, message)
        results.append((name, result))

    logger.info("\n" + "=" * 60)
    logger.info("Test Summary:")
    logger.info("=" * 60)
    for name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        logger.info(f"{name}: {status}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
