"""
SSE Transport Test

测试远程 SSE/Streamable HTTP MCP 服务器连接
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from core.config import ConfigManager, MCPServerConfigModel, MCPTransport
from core.mcp_manager import get_mcp_pool, reset_mcp_pool

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_sse_config():
    """测试 SSE 配置"""
    logger.info("=" * 60)
    logger.info("Test: SSE Configuration")
    logger.info("=" * 60)

    # 创建 SSE 服务器配置
    sse_config = MCPServerConfigModel(
        transport=MCPTransport.SSE,
        url="https://mcp.deepwiki.com/sse",
        description="Remote DeepWiki SSE server"
    )

    assert sse_config.transport == MCPTransport.SSE
    assert sse_config.url == "https://mcp.deepwiki.com/sse"
    assert sse_config.command is None  # SSE 不需要 command

    logger.info("✅ SSE configuration test passed")


async def test_sse_registration():
    """测试 SSE 服务器注册"""
    logger.info("=" * 60)
    logger.info("Test: SSE Server Registration")
    logger.info("=" * 60)

    # 重置池
    reset_mcp_pool()

    # 创建配置
    sse_config = MCPServerConfigModel(
        transport=MCPTransport.SSE,
        url="https://mcp.deepwiki.com/sse",
        description="Remote DeepWiki"
    )

    # 注册服务器
    pool = get_mcp_pool()
    pool.register_server("deepwiki-remote", sse_config)

    # 验证
    client = pool.get_client("deepwiki-remote")
    assert client.name == "deepwiki-remote"
    assert client.config.transport == MCPTransport.SSE
    assert client.config.url == "https://mcp.deepwiki.com/sse"

    logger.info("✅ SSE registration test passed")


async def test_validation():
    """测试配置验证"""
    logger.info("=" * 60)
    logger.info("Test: Configuration Validation")
    logger.info("=" * 60)

    # 测试：SSE 必须有 URL
    try:
        invalid_config = MCPServerConfigModel(
            transport=MCPTransport.SSE,
            # 缺少 url 字段
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        logger.info(f"✅ Validation caught missing URL: {e}")

    # 测试：stdio 必须有 command
    try:
        invalid_config = MCPServerConfigModel(
            transport=MCPTransport.STDIO,
            # 缺少 command 字段
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        logger.info(f"✅ Validation caught missing command: {e}")

    logger.info("✅ Validation test passed")


async def main():
    """运行所有测试"""
    try:
        await test_sse_config()
        await test_sse_registration()
        await test_validation()

        logger.info("=" * 60)
        logger.info("All SSE tests passed! ✅")
        logger.info("=" * 60)
        logger.info("")
        logger.info("远程 SSE 服务器配置示例：")
        logger.info("```yaml")
        logger.info("mcp_servers:")
        logger.info("  deepwiki-remote:")
        logger.info("    transport: sse  # 或 streamable_http")
        logger.info("    url: \"https://mcp.deepwiki.com/sse\"")
        logger.info("    description: \"GitHub repository exploration (remote)\"")
        logger.info("```")
        logger.info("")
        logger.info("优势：")
        logger.info("- ✅ 无需安装 npm 包")
        logger.info("- ✅ 无需配置 API Key")
        logger.info("- ✅ 开箱即用")
        logger.info("- ✅ 适合生产环境")

        return 0
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
