"""
A2A Agent Server - 主入口文件
启动一个符合A2A协议的HTTP服务器
"""

import logging
import uvicorn
from a2a.types import AgentCard, AgentSkill, AgentCapabilities
from a2a.server.apps.jsonrpc.fastapi_app import A2AFastAPIApplication
from a2a.server.request_handlers.default_request_handler import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from agent_executor import executor


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


# 定义Agent技能
echo_skill = AgentSkill(
    id="echo",
    name="Echo",
    description="Echoes back the user's message",
    example="Send any message and get it echoed back",
    tags=[],  # 添加必需的tags字段
)

# 创建Agent Card
agent_card = AgentCard(
    name="Echo Agent",
    description="A simple echo agent that demonstrates A2A protocol capabilities",
    version="1.0.0",
    skills=[echo_skill],
    input_modes=["text"],
    output_modes=["text"],
    streaming_support=True,
    capabilities=AgentCapabilities(streaming=True),  # 使用AgentCapabilities对象
    defaultInputModes=["text"],
    defaultOutputModes=["text"],
    url="http://localhost:9999",
)


def main():
    """启动A2A HTTP服务器"""
    # 配置服务器
    host = "0.0.0.0"
    port = 9999

    logger.info("Starting A2A Echo Agent Server...")
    logger.info(f"Agent Name: {agent_card.name}")
    logger.info(f"Agent Description: {agent_card.description}")
    logger.info(f"Server will be available at http://{host}:{port}")

    # 创建任务存储
    task_store = InMemoryTaskStore()

    # 创建请求处理器
    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=task_store,
    )

    # 创建FastAPI应用
    app_builder = A2AFastAPIApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    # 构建应用
    app = app_builder.build()

    try:
        # 运行服务器
        uvicorn.run(app, host=host, port=port)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    main()
