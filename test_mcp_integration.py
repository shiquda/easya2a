"""
MCP Integration Test

测试MCP集成的基本功能：
1. 配置加载
2. MCP服务器注册
3. MCP Agent创建
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from core.config import ConfigManager, MCPAgentConfigModel
from core.llm_manager import LLMManager, LLMConfig, register_llm_manager
from core.mcp_manager import get_mcp_pool, reset_mcp_pool
from agents.mcp import MCPAgent

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_config_loading():
    """测试1: 配置加载"""
    logger.info("=" * 60)
    logger.info("Test 1: Configuration Loading")
    logger.info("=" * 60)

    # 创建测试配置
    test_config = {
        "system": {
            "log_level": "DEBUG"
        },
        "llm_providers": {
            "test-llm": {
                "provider": "openai",
                "model": "gpt-4",
                "api_key": "test-key",
                "temperature": 0.7
            }
        },
        "mcp_servers": {
            "test-server": {
                "transport": "stdio",
                "command": "echo",
                "args": ["hello"],
                "description": "Test MCP server"
            }
        },
        "agents": [
            {
                "name": "test-agent",
                "description": "Test MCP agent",
                "type": "mcp",
                "host": "0.0.0.0",
                "port": 9999,
                "llm_provider": "test-llm",
                "extra": {
                    "mcp_config": {
                        "servers": ["test-server"],
                        "max_tool_calls": 3
                    }
                }
            }
        ]
    }

    # 加载配置
    config_manager = ConfigManager.load_from_dict(test_config)

    # 验证配置
    assert len(config_manager.get_all_mcp_servers()) == 1
    assert "test-server" in config_manager.get_all_mcp_servers()

    mcp_server_config = config_manager.get_mcp_server("test-server")
    assert mcp_server_config.command == "echo"
    assert mcp_server_config.description == "Test MCP server"

    logger.info("✅ Configuration loading test passed")
    return config_manager


async def test_mcp_pool():
    """测试2: MCP管理器池"""
    logger.info("=" * 60)
    logger.info("Test 2: MCP Manager Pool")
    logger.info("=" * 60)

    # 重置池
    reset_mcp_pool()

    # 创建简单配置
    from core.config import MCPServerConfigModel, MCPTransport

    mcp_config = MCPServerConfigModel(
        transport=MCPTransport.STDIO,
        command="echo",
        args=["test"],
        description="Test server"
    )

    # 注册服务器
    pool = get_mcp_pool()
    pool.register_server("test", mcp_config)

    # 验证注册
    client = pool.get_client("test")
    assert client.name == "test"
    assert client.config.command == "echo"

    logger.info("✅ MCP pool test passed")


async def test_mcp_agent_config():
    """测试3: MCP Agent配置"""
    logger.info("=" * 60)
    logger.info("Test 3: MCP Agent Configuration")
    logger.info("=" * 60)

    # 创建MCP Agent配置
    mcp_config = MCPAgentConfigModel(
        servers=["test-server", "another-server"],
        system_prompt="Test prompt",
        max_tool_calls=10,
        tool_choice="auto"
    )

    assert len(mcp_config.servers) == 2
    assert mcp_config.max_tool_calls == 10
    assert mcp_config.tool_choice == "auto"

    logger.info("✅ MCP Agent configuration test passed")


async def test_integration():
    """集成测试"""
    logger.info("=" * 60)
    logger.info("Integration Test: Full Workflow")
    logger.info("=" * 60)

    # 1. 加载配置
    config_manager = await test_config_loading()

    # 2. 测试MCP池
    await test_mcp_pool()

    # 3. 测试Agent配置
    await test_mcp_agent_config()

    logger.info("=" * 60)
    logger.info("All tests passed! ✅")
    logger.info("=" * 60)


async def main():
    """运行所有测试"""
    try:
        await test_integration()
        return 0
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
