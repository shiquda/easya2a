"""
Multi-Agent A2A Server - 主入口文件

从配置文件加载并启动多个符合A2A协议的Agent服务器
"""

import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI
from a2a.types import AgentCard, AgentSkill, AgentCapabilities
from a2a.server.apps.jsonrpc.fastapi_app import A2AFastAPIApplication
from a2a.server.request_handlers.default_request_handler import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore

from core.config import AgentConfigModel, initialize_config, get_config_manager
from core.server import MultiAgentServer
from core.llm_manager import LLMManager, LLMConfig, register_llm_manager

# Agent implementations
from agents.echo import EchoAgentExecutor
from agents.llm import create_llm_executor


logger = logging.getLogger(__name__)


def build_agent_card(agent_config: AgentConfigModel) -> AgentCard:
    """
    根据配置构建Agent Card

    Args:
        agent_config: Agent配置

    Returns:
        AgentCard对象
    """
    # 基础技能（可以根据agent类型自定义）
    skill = AgentSkill(
        id=agent_config.type,
        name=agent_config.name,
        description=agent_config.description,
        example=f"Interact with {agent_config.name}",
        tags=[agent_config.type],
    )

    # 构建Agent Card
    card = AgentCard(
        name=agent_config.name,
        description=agent_config.description,
        version="1.0.0",
        skills=[skill],
        input_modes=["text"],
        output_modes=["text"],
        streaming_support=True,
        capabilities=AgentCapabilities(streaming=True),
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        url=agent_config.url,
    )

    # 添加provider信息（如果有）
    if agent_config.provider:
        provider_info = {"organization": agent_config.provider.organization}
        # 只添加非None的字段
        if agent_config.provider.url:
            provider_info["url"] = agent_config.provider.url
        if agent_config.provider.email:
            provider_info["email"] = agent_config.provider.email
        card.provider = provider_info

    return card


def build_agent_executor(agent_config: AgentConfigModel):
    """
    根据配置构建Agent Executor

    Args:
        agent_config: Agent配置

    Returns:
        AgentExecutor实例

    Raises:
        ValueError: 不支持的agent类型或缺少必要配置
    """
    if agent_config.type == "echo":
        # Echo Agent
        return EchoAgentExecutor(name=agent_config.name)

    elif agent_config.type == "llm":
        # LLM Agent
        if not agent_config.llm_provider:
            raise ValueError(
                f"LLM agent '{agent_config.name}' requires llm_provider field"
            )

        # 从全局配置获取LLM provider配置
        config_manager = get_config_manager()
        llm_config_model = config_manager.get_llm_provider(agent_config.llm_provider)

        # 转换为LLMConfig并注册LLM管理器
        llm_config = LLMConfig(**llm_config_model.model_dump())
        llm_manager = register_llm_manager(agent_config.name, llm_config)

        # 获取system prompt
        system_prompt = agent_config.extra.get("system_prompt")

        # 创建executor
        return create_llm_executor(
            llm_manager=llm_manager,
            name=agent_config.name,
            system_prompt=system_prompt,
        )

    else:
        raise ValueError(f"Unsupported agent type: {agent_config.type}")


def build_fastapi_app(agent_config: AgentConfigModel) -> FastAPI:
    """
    为单个Agent构建FastAPI应用

    Args:
        agent_config: Agent配置

    Returns:
        FastAPI应用实例
    """
    logger.info(f"Building FastAPI app for agent '{agent_config.name}'...")

    # 构建Agent Card
    agent_card = build_agent_card(agent_config)

    # 构建Agent Executor
    agent_executor = build_agent_executor(agent_config)

    # 创建任务存储
    task_store = InMemoryTaskStore()

    # 创建请求处理器
    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor,
        task_store=task_store,
    )

    # 创建FastAPI应用
    app_builder = A2AFastAPIApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    # 构建应用
    app = app_builder.build()

    logger.info(
        f"Agent '{agent_config.name}' ({agent_config.type}) "
        f"will be available at {agent_config.url}"
    )

    return app


async def main():
    """启动多Agent服务器"""
    # 配置文件路径
    config_path = Path(__file__).parent / "config" / "agents.yaml"

    logger.info("=" * 60)
    logger.info("Multi-Agent A2A Server Starting...")
    logger.info("=" * 60)

    try:
        # 创建并启动服务器
        server = MultiAgentServer(
            config_path=str(config_path),
            app_builder=build_fastapi_app,
        )

        # 运行服务器（阻塞直到收到关闭信号）
        await server.run()

    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        logger.error(f"Please create {config_path}")
        raise
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nServer stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        exit(1)
